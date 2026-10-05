"""Emissores por plataforma. Cada um devolve Artifacts (nada é escrito aqui).

Formatos e fontes oficiais: references/platforms.md. Camadas: references/ARCHITECTURE.md §8-ter.
"""
import re
from pathlib import Path
from cslib.paths import STATE_DIR

from emit import j5, maps, render
from emit.common import (GEN_MARK, GEN_MARK_TOML, GEN_TOKEN, WRITE_TOOLS, EmitError, expand_braces, frontmatter,
                         template, toml_multiline, toml_str, yq)

OWNED = "owned"   # arquivo inteiro é gerado (carrega GEN_MARK)
BLOCK = "block"   # só o bloco entre marcadores é gerado; o resto é humano
SHARED = "shared"  # artefato neutro (.swarm/...) usado por mais de uma plataforma
MAPS = "maps"      # .swarm/knowledge/*.json5 — sempre emitidos


class Artifact(object):
    __slots__ = ("platform", "kind", "layer", "path", "mode", "content", "agent")

    def __init__(self, platform, kind, layer, path, mode, content, agent=None):
        self.platform, self.kind, self.layer, self.path = platform, kind, layer, path
        self.mode, self.content, self.agent = mode, content, agent

    def __repr__(self):
        return "Artifact(%s, %s)" % (self.kind, self.path)


def is_gate(agent):
    return agent["kind"] == "gate"


def writes(agent):
    return any(t in WRITE_TOOLS for t in agent["tools"]) and not is_gate(agent)


def owned_md(fm_pairs, body):
    head = (frontmatter(fm_pairs) + "\n") if fm_pairs else ""
    return "%s%s\n\n%s" % (head, GEN_MARK, body.rstrip("\n") + "\n")


def s0_plus_kernel(team, s1_pointer):
    """Plataformas sem arquivo sempre-carregado separado: núcleo S0 + kernel no mesmo bloco."""
    return render.s0_fit(team, s1_pointer) + "\n" + render.orchestrator_kernel(team)


def territory_agents(team):
    return [a for a in team["agents"] if a.get("territory")]


def shared_playbook_path(name):
    return ".swarm/playbooks/%s.json5" % name


def shared_territory_path(name):
    return ".swarm/territories/%s.json5" % name


def owned_j5(obj, what):
    return j5.dumps(obj, "%s: %s; não edite: altere team.json5 e rode `cs.py emit`" % (GEN_TOKEN, what))


def routing_floor(root, agent):
    """Piso de modelo de um gate declarado em .swarm/routing.json5 (senão None)."""
    if not is_gate(agent):
        return None
    for rel in ("routing.json5", "state/routing.json5"):
        p = Path(root) / STATE_DIR / rel
        if p.is_file():
            try:
                data = j5.load(p)
            except ValueError as exc:
                raise EmitError("%s ilegível: %s" % (p, exc))
            floors = data.get("floors") or data.get("gate_floors") or {}
            per = (data.get("agents") or {}).get(agent["name"]) or {}
            val = floors.get(agent["name"]) or per.get("floor") or data.get("gate_floor")
            if isinstance(val, dict):
                val = val.get("claude-code")
            return val
    return None


class Ctx(object):
    """Estado compartilhado de uma emissão (para fonte única entre S1 e S2)."""

    def __init__(self, team, kn, root):
        self.team, self.kn, self.root = team, kn, root
        self.shared = {}  # path -> Artifact neutro

    def add_shared(self, art):
        self.shared.setdefault(art.path, art)


def _shared_playbooks(ctx, ag):
    if render.has_playbooks(ag):
        data = {"agent": ag["name"], "playbooks": [{"title": p["title"], "steps": list(p["steps"])}
                                                   for p in ag["card"]["playbooks"]]}
        ctx.add_shared(Artifact(SHARED, "shared.playbooks", "S4", shared_playbook_path(ag["name"]), OWNED,
                                owned_j5(data, "playbooks (S4) de %s" % ag["name"]), ag["name"]))
        return shared_playbook_path(ag["name"])
    return None


# ------------------------------------------------------------------ Claude Code

ORCH_CLAUDE = ".claude/orchestrator.md"
ORCH_CURSOR = ".cursor/rules/cs-orchestrator.mdc"

SESSION_SKILLS = (
    ("salvar-sessao", "session-save.md",
     "Salva a sessão via `.swarm/bin/cs-session save` (feito/próximo/bloqueio em 1 linha cada).",
     [("argument-hint", yq("[--commit]")), ("allowed-tools", yq("Bash(.swarm/bin/cs-session save *)"))]),
    ("carregar-sessao", "session-load.md",
     "Retoma a sessão: injeta o briefing de `.swarm/bin/cs-session load` sem ler arquivos de estado.",
     [("allowed-tools", yq("Bash(.swarm/bin/cs-session load *)"))]),
)

# Skills de estado (árvore de trabalho): finas, tudo mecânico no `cs-state`. Consulta e criação são
# model-invocable; mudança de estado exige o humano (disable-model-invocation: true).
STATE_SKILLS = (
    ("board", False, "[--json]", ("board", "tree", "find"),
     "Mostra o quadro de trabalho (épicos, sprints, features, stories, tasks) via `cs-state board`/`tree --json`."),
    ("new-epico", False, "<título> -- <objetivo> [-- <métrica>]", ("new epico", "board"),
     "Cria um épico via `cs-state new epico` (mostra antes com --dry-run). Use quando o usuário pedir um épico novo."),
    ("new-sprint", False, "<meta> [<EPC>]", ("new sprint", "board"),
     "Cria uma sprint via `cs-state new sprint` (mostra antes com --dry-run). Use quando o usuário pedir uma sprint nova."),
    ("new-feature", False, "<título> <SPR|--backlog> <comando de aceite>", ("new feature", "check", "board"),
     "Cria uma feature via `cs-state new feature` com teste de aceite (mostra antes com --dry-run; DoR por `cs-state check`)."),
    ("new-task", False, "<US|BUG|FIX|CHORE> <pai> <título>", ("new task", "check", "board"),
     "Cria uma task US/BUG/FIX/CHORE via `cs-state new task` (mostra antes com --dry-run; DoR por `cs-state check`). "
     "Use antes de qualquer alteração de produto sem task em andamento."),
    ("new-story", False, "<US|BUG|FIX> <FEA> <agentes> <título>", ("new story", "check", "board"),
     "Cria uma story (1 agente: task tipada; 2+: story composta) via `cs-state new story` (dry-run antes; DoR por `cs-state check`)."),
    ("close-task", True, "<id da task> <resumo>", ("close", "board"),
     "Fecha uma task via `cs-state close` (o motor confere o DoD e arquiva)."),
    ("close-feature", True, "<FEA> <resumo>", ("close", "board"),
     "Fecha uma feature via `cs-state close` (o motor confere o DoD e arquiva)."),
    ("close-sprint", True, "<SPR> <resumo>", ("close", "board"),
     "Fecha uma sprint via `cs-state close` (o motor confere o DoD e arquiva)."),
    ("close-epico", True, "<EPC> <resumo>", ("close", "board"),
     "Fecha um épico via `cs-state close` (o motor confere o DoD e arquiva)."),
    ("close-story", True, "<US|BUG|FIX id> <resumo>", ("close", "board"),
     "Fecha uma story composta via `cs-state close` (só com todas as tasks fechadas)."),
    ("reopen", True, "<id> <motivo>", ("reopen", "find", "tree"),
     "Reabre um item fechado via `cs-state reopen` (volta ao mesmo caminho, com motivo)."),
    ("park", True, "<FEA> <motivo>", ("park", "board"),
     "Estaciona uma feature ativa via `cs-state park` (sai de execução com motivo)."),
    ("move", True, "<id> <novo pai|--avulsa>", ("move", "board"),
     "Troca o pai de um item via `cs-state move` (o id antigo continua resolvendo em `find`)."),
)
STATE_SKILL_NAMES = tuple(s[0] for s in STATE_SKILLS)
STATE_SKILLS_HUMAN = tuple(s[0] for s in STATE_SKILLS if s[1])


def state_skills():
    """Artifacts das 14 skills de estado (Claude Code). Corpo em assets/templates/state/<nome>.md."""
    arts = []
    for name, human, hint, cmds, desc in STATE_SKILLS:
        tools = " ".join("Bash(.swarm/bin/cs-state %s *)" % c for c in cmds)
        fm = [("name", name), ("description", yq(desc))]
        if human:
            fm.append(("disable-model-invocation", "true"))
        fm += [("argument-hint", yq(hint)), ("allowed-tools", yq(tools))]
        arts.append(Artifact("claude-code", "claude.state", "STATE", ".claude/skills/%s/SKILL.md" % name,
                             OWNED, owned_md(fm, template("state/%s.md" % name))))
    return arts


def claude_code(ctx):
    team, arts = ctx.team, []
    for ag in team["agents"]:
        n = ag["name"]
        skill_dir = "%s-playbooks" % n
        pointers = {"s2": ".claude/rules/cs-%s.md" % n if ag.get("territory") else None,
                    "s4": ".claude/skills/%s/SKILL.md" % skill_dir if render.has_playbooks(ag) else None}
        body, st, sr = render.s1_fit(team, ag, ctx.kn, pointers)
        fm = [("name", n),
              ("description", yq(ag["card"]["description"])),
              ("tools", ", ".join(ag["tools"])),
              ("model", routing_floor(ctx.root, ag) or "inherit"),  # tier é decidido por despacho (cs-route)
              ("memory", "project")]
        if is_gate(ag):
            fm.append(("disallowedTools", ", ".join(WRITE_TOOLS)))
        arts.append(Artifact("claude-code", "claude.agent", "S1", ".claude/agents/%s.md" % n, OWNED,
                             owned_md(fm, body), n))
        if pointers["s4"]:
            titles = "; ".join(p["title"] for p in ag["card"]["playbooks"])
            desc = "Procedimentos passo a passo de %s neste repo. Use quando %s for executar: %s" % (n, n, titles)
            sfm = [("name", skill_dir), ("description", yq(desc[:1400]))]
            arts.append(Artifact("claude-code", "claude.skill", "S4", pointers["s4"], OWNED,
                                 owned_md(sfm, render.s4_playbooks(ag)), n))
        if pointers["s2"]:
            arts.append(Artifact("claude-code", "claude.rule", "S2", pointers["s2"], OWNED,
                                 owned_md([("paths", list(ag["territory"]))],
                                          render.s2_body(team, ag, ctx.kn, st, sr)), n))
    for cmd, tpl, desc, extra in SESSION_SKILLS:
        sfm = [("name", cmd), ("description", yq(desc)), ("disable-model-invocation", "true")] + extra
        arts.append(Artifact("claude-code", "claude.session", "SESSION", ".claude/skills/%s/SKILL.md" % cmd,
                             OWNED, owned_md(sfm, template(tpl))))
    arts.append(Artifact("claude-code", "claude.memory", "S0", "CLAUDE.md", BLOCK,
                         render.s0_fit(team, ".claude/agents/{n}.md", "native", render.orch_pointer(ORCH_CLAUDE))))
    cfm = [("name", "corrigir"),
           ("description", yq("Registra a correção do usuário como lição do agente que errou (`.swarm/bin/cs-mem correct`).")),
           ("disable-model-invocation", "true"),
           ("argument-hint", yq("<agente> <o que estava errado> -> <o certo>, porque <porquê>")),
           ("allowed-tools", yq("Bash(.swarm/bin/cs-mem correct *)"))]
    arts.append(Artifact("claude-code", "claude.session", "SESSION", ".claude/skills/corrigir/SKILL.md",
                         OWNED, owned_md(cfm, template("corrigir.md"))))
    pfm = [("name", "planejar-sprint"),
           ("description", yq("Planeja a próxima sprint com stories que passam no DoR, via `.swarm/bin/cs-state sprint plan`.")),
           ("disable-model-invocation", "true"),
           ("argument-hint", yq("[--dry-run]"))]
    arts.append(Artifact("claude-code", "claude.command", "CMD", ".claude/skills/planejar-sprint/SKILL.md",
                         OWNED, owned_md(pfm, template("planejar-sprint.md"))))
    afm = [("name", "feature-autonoma"),
           ("description", yq("Inicia o modo autônomo de uma feature: aprovação única de spec, testes de aceite, "
                              "classe e orçamento; depois `.swarm/bin/cs-state next` até o relatório.")),
           ("disable-model-invocation", "true"),
           ("argument-hint", yq("<feature-id> <arquivo-spec>")),
           ("arguments", "[feature, spec]")]
    arts.append(Artifact("claude-code", "claude.command", "CMD", ".claude/skills/feature-autonoma/SKILL.md",
                         OWNED, owned_md(afm, template("feature-autonoma.md"))))
    arts.extend(state_skills())
    arts.append(Artifact("claude-code", "claude.orchestrator", "ORCH", ORCH_CLAUDE, OWNED,
                         owned_md(None, render.orchestrator_kernel(team))))
    return arts


# ------------------------------------------------------------------ Cursor

def cursor(ctx):
    team, arts = ctx.team, []
    core_fm = [("description", yq("Núcleo do repositório e mapa de agentes (codebase-specialists)")),
               ("alwaysApply", "true")]
    arts.append(Artifact("cursor", "cursor.rule.core", "S0", ".cursor/rules/cs-core.mdc", OWNED,
                         owned_md(core_fm, render.s0_fit(team, ".cursor/agents/{n}.md",
                                                         orchestrator_line=render.orch_pointer(ORCH_CURSOR)))))
    ofm = [("description", yq("Kernel do orquestrador (agente principal)")), ("alwaysApply", "true")]
    arts.append(Artifact("cursor", "cursor.rule.orchestrator", "ORCH", ORCH_CURSOR, OWNED,
                         owned_md(ofm, render.orchestrator_kernel(team))))
    for ag in team["agents"]:
        n = ag["name"]
        pointers = {"s2": ".cursor/rules/cs-%s.mdc" % n if ag.get("territory") else None,
                    "s4": _shared_playbooks(ctx, ag)}
        body, st, sr = render.s1_fit(team, ag, ctx.kn, pointers)
        fm = [("name", n), ("description", yq(ag["card"]["description"])), ("model", "inherit"),
              ("readonly", "false" if writes(ag) else "true")]
        arts.append(Artifact("cursor", "cursor.agent", "S1", ".cursor/agents/%s.md" % n, OWNED,
                             owned_md(fm, body), n))
        if pointers["s2"]:
            rfm = [("description", yq("Regras do território de %s" % n)),
                   ("globs", ",".join(expand_braces(ag["territory"]))),  # vírgulas, sem aspas (docs Cursor)
                   ("alwaysApply", "false")]
            arts.append(Artifact("cursor", "cursor.rule.territory", "S2", pointers["s2"], OWNED,
                                 owned_md(rfm, render.s2_body(team, ag, ctx.kn, st, sr)), n))
    return arts


# ------------------------------------------------------------------ GitHub Copilot

COPILOT_TOOL_MAP = (("read", ("Read", "NotebookRead")),
                    ("search", ("Grep", "Glob", "LS")),
                    ("edit", ("Edit", "Write", "MultiEdit", "NotebookEdit")),
                    ("execute", ("Bash",)),
                    ("web", ("WebFetch", "WebSearch")))
COPILOT_ALIASES = ("read", "search", "edit", "execute", "web", "agent", "todo")


def copilot_tools(agent):
    out = []
    for alias, names in COPILOT_TOOL_MAP:
        if alias == "edit" and is_gate(agent):
            continue
        if any(t in names for t in agent["tools"]):
            out.append(alias)
    return out


def copilot(ctx):
    team = ctx.team
    arts = [Artifact("copilot", "copilot.instructions", "S0", ".github/copilot-instructions.md", BLOCK,
                     s0_plus_kernel(team, ".github/agents/{n}.agent.md"))]
    for ag in team["agents"]:
        n = ag["name"]
        pointers = {"s2": ".github/instructions/cs-%s.instructions.md" % n if ag.get("territory") else None,
                    "s4": _shared_playbooks(ctx, ag)}
        body, st, sr = render.s1_fit(team, ag, ctx.kn, pointers)
        tools = "[%s]" % ", ".join(yq(t) for t in copilot_tools(ag))
        fm = [("name", n), ("description", yq(ag["card"]["description"])), ("tools", tools)]
        arts.append(Artifact("copilot", "copilot.agent", "S1", ".github/agents/%s.agent.md" % n, OWNED,
                             owned_md(fm, body), n))
        if pointers["s2"]:
            ifm = [("applyTo", yq(",".join(expand_braces(ag["territory"]))))]
            arts.append(Artifact("copilot", "copilot.instructions.path", "S2", pointers["s2"], OWNED,
                                 owned_md(ifm, render.s2_body(team, ag, ctx.kn, st, sr)), n))
    return arts


# ------------------------------------------------------------------ Codex / AGENTS.md

STATIC_DIR = re.compile(r"^([^*?\[\]{}]+?)/\*\*(?:/\*)?$")


def nested_dir_map(agent, root):
    """Diretórios para AGENTS.md aninhado, ou None se algum glob não for `dir/**` existente."""
    dirs = []
    for glob in agent.get("territory") or []:
        m = STATIC_DIR.match(glob)
        if not m:
            return None
        d = m.group(1).strip("/")
        if not d or d.startswith(".") or not (Path(root) / d).is_dir():
            return None
        dirs.append(d)
    return dirs or None


COPY_RE = re.compile(r"^\s*(?:COPY|ADD)\s+(?:--\S+\s+)*(.+)$", re.I | re.M)


def shipped_dirs(root):
    """Diretórios que um Dockerfile copia para a imagem (None = copia a raiz inteira).

    AGENTS.md aninhado nessas pastas iria para o artefato de build; o S2 vai para o arquivo
    de território compartilhado. `.dockerignore` que exclua AGENTS.md libera o aninhamento.
    """
    root = Path(root)
    ign = root / ".dockerignore"
    if ign.is_file() and re.search(r"(^|/|\*\*/)AGENTS\.md\s*$", ign.read_text(errors="replace"), re.M):
        return set()
    out = set()
    for df in list(root.glob("Dockerfile*")) + list(root.glob("*/Dockerfile*")) + list(root.glob("*.Dockerfile")):
        if not df.is_file():
            continue
        for m in COPY_RE.finditer(df.read_text(errors="replace")):
            parts = m.group(1).split()
            if parts and parts[0].startswith("["):
                continue  # forma JSON: conservador, trata como raiz
            for src in parts[:-1]:
                src = src.strip("./") if src not in (".", "./") else ""
                if src == "":
                    return None
                out.add(src.split("/")[0])
    return out


def codex(ctx):
    team, arts = ctx.team, []
    arts.append(Artifact("codex", "codex.agents_md", "S0", "AGENTS.md", BLOCK,
                         s0_plus_kernel(team, ".codex/agents/{n}.toml")))
    by_dir, shown = {}, {}
    shipped = shipped_dirs(ctx.root)
    for ag in team["agents"]:
        n = ag["name"]
        dirs = nested_dir_map(ag, ctx.root) if ag.get("territory") else None
        if dirs and (shipped is None or any(d.split("/")[0] in shipped for d in dirs)):
            dirs = None  # pasta vai para a imagem de build: S2 no arquivo compartilhado
        if dirs:
            s2 = ", ".join("%s/AGENTS.md" % d for d in dirs)
        elif ag.get("territory"):
            s2 = shared_territory_path(n)
        else:
            s2 = None
        pointers = {"s2": s2, "s4": _shared_playbooks(ctx, ag)}
        body, st, sr = render.s1_fit(team, ag, ctx.kn, pointers)
        shown[n] = (st, sr)
        if dirs:
            for d in dirs:
                by_dir.setdefault(d, []).append(ag)
        elif s2:
            ctx.add_shared(Artifact(SHARED, "shared.territory", "S2F", s2, OWNED,
                                    owned_j5(render.s2_data(ag, ctx.kn, st, sr), "território (S2) de %s" % n), n))
        content = "\n".join([
            GEN_MARK_TOML,
            "name = %s" % toml_str(n),
            "description = %s" % toml_str(ag["card"]["description"]),
            "sandbox_mode = %s" % toml_str("workspace-write" if writes(ag) else "read-only"),
            "developer_instructions = %s" % toml_multiline(body),
        ]) + "\n"
        arts.append(Artifact("codex", "codex.agent", "S1", ".codex/agents/%s.toml" % n, OWNED, content, n))
    for d, agents in sorted(by_dir.items()):
        arts.append(Artifact("codex", "codex.agents_md.nested", "S2", "%s/AGENTS.md" % d, BLOCK,
                             render.nested_block(team, agents, ctx.kn, shown)))
    return arts


EMITTERS = {"claude-code": claude_code, "cursor": cursor, "copilot": copilot, "codex": codex}


def build(team, kn, root, platforms):
    ctx = Ctx(team, kn, root)
    arts = []
    for p in platforms:
        arts.extend(EMITTERS[p](ctx))
    arts.extend(ctx.shared.values())
    s5 = render.s5_items(team)
    if s5:  # camadas.s5_memoria dos cartões → indexado por cs-mem (fonte única: não aparece em S0–S2)
        arts.append(Artifact(MAPS, "maps.s5-memoria", "S5", "%s/s5-memoria.json5" % maps.KNOW_DIR, OWNED,
                             owned_j5({"schema_version": 1, "items": s5},
                                      "S5 memória (camadas.s5_memoria dos cartões), lida por cs-mem search")))
    for ag in team["agents"]:  # lista completa e priorizada de invariantes (o cartão do gate aponta para ela)
        if render.invariant_count(ag, kn.facts):
            arts.append(Artifact(MAPS, "maps.invariants", "S5", render.invariants_path(ag["name"]), OWNED,
                                 owned_j5(render.invariants_data(ag, kn.facts),
                                          "invariantes de %s (lista completa, priorizada)" % ag["name"]), ag["name"]))
    texts, _ = maps.build(root, team)
    for name in sorted(texts):
        arts.append(Artifact(MAPS, "maps." + name.split(".")[0], "S5", "%s/%s" % (maps.KNOW_DIR, name), OWNED,
                             texts[name]))
    paths = [a.path for a in arts]
    dup = sorted({p for p in paths if paths.count(p) > 1})
    if dup:
        raise EmitError("dois artefatos no mesmo caminho: %s" % dup)
    return sorted(arts, key=lambda a: a.path)


def manifest_platforms(platforms):
    """Plataformas cujo manifesto esta emissão governa (SHARED vai junto de qualquer não-Claude)."""
    out = set(platforms) | {MAPS}
    if out - {"claude-code", MAPS}:
        out.add(SHARED)
    return out
