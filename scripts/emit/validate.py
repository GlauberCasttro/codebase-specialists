"""Validador de formato por plataforma — gate G7. Falha alto.

Lê o que está NO DISCO e confere, por artefato esperado (recalculado de team.json):
- existência; marcador de gerado (arquivo inteiro) ou bloco bem-formado (begin/end exatamente 1x);
- frescor: conteúdo gerado == o que `cs.py emit` produziria agora (edição manual = falha);
- frontmatter/campos obrigatórios e valores permitidos de cada plataforma (references/platforms.md);
- gate sem ferramenta de escrita em toda plataforma; veredito só do veredito_enum;
- orçamento por camada de steering (S0 ≤40, S1 ≤80, S2 ≤60, kernel ≤80, comandos de sessão ≤15);
- órfãos: arquivo com marcador de gerado que não corresponde a nenhum agente atual.
"""
from pathlib import Path

from emit import j5, knowledge, maps, platforms as P, render
from emit.common import (GEN_TOKEN, FrontmatterError, WRITE_TOOLS, block_inner, find_block,
                         parse_frontmatter, parse_toml, read_text)
from emit.team import KNOWN_CLAUDE_TOOLS, MAX_DESC, NAME_RE, foreign_verdicts, load_team, \
    resolve_invariants, veredito_enum

CLAUDE_AGENT_KEYS = {"name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
                     "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd", "effort",
                     "isolation", "color", "initialPrompt", "experimental"}
CLAUDE_MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
CLAUDE_SKILL_KEYS = {"name", "description", "when_to_use", "argument-hint", "arguments",
                     "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools", "model",
                     "effort", "context", "agent", "background", "hooks", "paths", "shell", "metadata",
                     "license", "compatibility"}
CURSOR_RULE_KEYS = {"description", "globs", "alwaysApply"}
CURSOR_AGENT_KEYS = {"name", "description", "model", "readonly", "is_background"}
CURSOR_SKILL_KEYS = {"name", "description", "disable-model-invocation", "license", "compatibility", "metadata"}
COPILOT_SKILL_KEYS = {"name", "description", "argument-hint", "user-invokable", "disable-model-invocation",
                      "license", "compatibility", "metadata"}
CODEX_SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata"}
PORTABLE_SKILL_KEYS = {"cursor.skill": CURSOR_SKILL_KEYS, "copilot.skill": COPILOT_SKILL_KEYS,
                       "codex.skill": CODEX_SKILL_KEYS}
COPILOT_AGENT_KEYS = {"name", "description", "target", "tools", "model", "disable-model-invocation",
                      "user-invocable", "mcp-servers", "metadata"}
CODEX_SANDBOX = {"read-only", "workspace-write"}
CODEX_MAX_BYTES = 32 * 1024
COPILOT_MAX_CHARS = 30000
GEN_DIRS = (".claude/agents", ".claude/rules", ".claude/skills", ".cursor/rules", ".cursor/agents",
            ".cursor/skills", ".github/agents", ".github/instructions", ".github/skills", ".codex/agents",
            ".agents/skills", ".swarm/playbooks",
            ".swarm/territories", ".swarm/knowledge")


class Report(object):
    def __init__(self):
        self.errors, self.checked = [], 0

    def fail(self, path, msg):
        self.errors.append("%s: %s" % (path, msg))

    @property
    def ok(self):
        return not self.errors


def _strip_marker(body):
    lines = body.split("\n")
    while lines and (not lines[0].strip() or GEN_TOKEN in lines[0]):
        lines.pop(0)
    return "\n".join(lines)


def _fm(rep, path, text):
    try:
        fm, body = parse_frontmatter(text)
        return fm, _strip_marker(body)
    except FrontmatterError as exc:
        rep.fail(path, "frontmatter inválido: %s" % exc)
        return None, None


def _unknown(rep, path, fm, allowed):
    extra = sorted(set(fm) - allowed)
    if extra:
        rep.fail(path, "campos de frontmatter desconhecidos: %s" % extra)


def _desc(rep, path, fm, limit=MAX_DESC, required=True):
    d = fm.get("description")
    if d in (None, "", []):
        if required:
            rep.fail(path, "description obrigatória ausente")
        return
    if not isinstance(d, str):
        rep.fail(path, "description deve ser string")
    elif len(d) > limit:
        rep.fail(path, "description com %d caracteres (máx %d)" % (len(d), limit))


def _tool_list(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _budget(rep, path, layer, text):
    limit = render.BUDGET.get(layer)
    if limit is None:
        return
    n = render.count_lines(text)
    if n > limit:
        nxt = {"S0": "S2 (território)", "S1": "S2/S4", "S2": "S4/S5 (memória)", "ORCH": "references/harness.md",
               "SESSION": "o script cs-session", "CMD": "o kernel/cs-state",
               "STATE": "o script cs-state"}.get(layer, "a camada seguinte")
        rep.fail(path, "orçamento %s estourado: %d linhas > %d; mova o excedente para %s" % (layer, n, limit, nxt))


def _gate_verdicts(rep, path, team, agent, text):
    if agent and agent["kind"] == "gate":
        bad = foreign_verdicts(text, veredito_enum(team))
        if bad:
            rep.fail(path, "veredito fora do veredito_enum: %s" % bad)


# ------------------------------------------------------------------ checkers por tipo

def check_claude_agent(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, CLAUDE_AGENT_KEYS)
    name = fm.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name) or ":" in name:
        rep.fail(art.path, "name inválido: %r" % name)
    elif Path(art.path).stem != name:
        rep.fail(art.path, "nome do arquivo difere de name (%s)" % name)
    _desc(rep, art.path, fm)
    tools = _tool_list(fm.get("tools", ""))
    if not tools:
        rep.fail(art.path, "tools vazio (agente sem ferramentas não sobe)")
    unknown = [t for t in tools if t not in KNOWN_CLAUDE_TOOLS and not t.startswith("mcp__")]
    if unknown:
        rep.fail(art.path, "tools desconhecidas: %s" % unknown)
    model = fm.get("model", "inherit")
    if model not in CLAUDE_MODELS and not str(model).startswith("claude-"):
        rep.fail(art.path, "model inválido: %r" % model)
    if agent and agent["kind"] != "gate" and model != "inherit":
        rep.fail(art.path, "model deve ser inherit (tier decidido por despacho via cs-route)")
    if "memory" in fm and fm["memory"] not in ("user", "project", "local"):
        rep.fail(art.path, "memory deve ser user|project|local")
    if agent and agent["kind"] == "gate":
        w = [t for t in tools if t in WRITE_TOOLS]
        if w:
            rep.fail(art.path, "gate com ferramenta de escrita: %s" % w)
        dis = set(_tool_list(fm.get("disallowedTools", "")))
        if not {"Edit", "Write"} <= dis:
            rep.fail(art.path, "gate sem disallowedTools Edit/Write")
    return body


def check_claude_rule(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, {"paths"})
    paths = fm.get("paths")
    if isinstance(paths, str):
        paths = [p.strip() for p in paths.split(",") if p.strip()]
    if not paths:
        rep.fail(art.path, "paths ausente ou vazio (regra viraria sempre-carregada)")
    return body


def check_claude_skill(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, CLAUDE_SKILL_KEYS)
    dirname = Path(art.path).parent.name
    if fm.get("name", dirname) != dirname:
        rep.fail(art.path, "name %r difere do diretório %r" % (fm.get("name"), dirname))
    _desc(rep, art.path, fm, limit=1536)
    if art.layer in ("SESSION", "CMD") and fm.get("disable-model-invocation") is not True:
        rep.fail(art.path, "comando deve ter disable-model-invocation: true")
    if art.layer == "STATE":
        human = dirname in P.STATE_SKILLS_HUMAN
        if human and fm.get("disable-model-invocation") is not True:
            rep.fail(art.path, "skill que muda estado deve ter disable-model-invocation: true")
        if not human and fm.get("disable-model-invocation") is True:
            rep.fail(art.path, "skill de consulta/criação deve ser invocável pelo modelo")
    if art.layer == "SESSION":
        _budget(rep, art.path, "SESSION", text)  # orçamento do arquivo inteiro
        return None
    return body


def check_portable_skill(rep, art, text, team, agent):
    """Skill de estado/mandato em Cursor (.cursor/skills), Copilot (.github/skills) ou Codex (.agents/skills)."""
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, PORTABLE_SKILL_KEYS[art.kind])
    dirname = Path(art.path).parent.name
    if fm.get("name") != dirname:
        rep.fail(art.path, "name %r difere do diretório %r" % (fm.get("name"), dirname))
    _desc(rep, art.path, fm, limit=1024)
    human = dirname in P.STATE_SKILLS_HUMAN
    dmi = fm.get("disable-model-invocation")
    if art.kind == "codex.skill":
        says = P.HUMAN_ONLY_TEXT.casefold() in body.casefold()
        if human and not says:
            rep.fail(art.path, "skill humana no Codex (sem disable-model-invocation) deve dizer '%s'"
                     % P.HUMAN_ONLY_TEXT)
        if not human and says:
            rep.fail(art.path, "skill de consulta/criação não pode dizer '%s'" % P.HUMAN_ONLY_TEXT)
    else:
        if human and dmi is not True:
            rep.fail(art.path, "skill que muda estado deve ter disable-model-invocation: true")
        if not human and dmi is True:
            rep.fail(art.path, "skill de consulta/criação deve ser invocável pelo modelo")
    return body


def check_plain(rep, art, text, team, agent):
    return _strip_marker(text)


def check_json5(rep, art, text, team, agent):
    try:
        j5.loads(text)
    except ValueError as exc:
        rep.fail(art.path, "JSON5 inválido: %s" % exc)
    return None


def check_cursor_rule(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, CURSOR_RULE_KEYS)
    _desc(rep, art.path, fm)
    aa = fm.get("alwaysApply")
    if not isinstance(aa, bool):
        rep.fail(art.path, "alwaysApply deve ser booleano")
    if art.kind in ("cursor.rule.core", "cursor.rule.orchestrator"):
        if aa is not True:
            rep.fail(art.path, "núcleo/kernel precisa de alwaysApply: true")
    else:
        globs = fm.get("globs")
        if aa is not False:
            rep.fail(art.path, "regra de território precisa de alwaysApply: false")
        if not isinstance(globs, str) or not globs.strip():
            rep.fail(art.path, "globs ausente (string separada por vírgulas)")
        elif "{" in globs:
            rep.fail(art.path, "globs com chaves {a,b} quebra a separação por vírgula")
    if not art.path.endswith(".mdc"):
        rep.fail(art.path, "regra do Cursor precisa da extensão .mdc")
    return body


def check_cursor_agent(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, CURSOR_AGENT_KEYS)
    name = fm.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        rep.fail(art.path, "name inválido: %r" % name)
    _desc(rep, art.path, fm)
    if not isinstance(fm.get("readonly", False), bool):
        rep.fail(art.path, "readonly deve ser booleano")
    if agent and agent["kind"] == "gate" and fm.get("readonly") is not True:
        rep.fail(art.path, "gate precisa de readonly: true")
    return body


def check_copilot_path(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, {"applyTo", "excludeAgent", "description", "name"})
    at = fm.get("applyTo")
    if not isinstance(at, str) or not at.strip():
        rep.fail(art.path, "applyTo ausente")
    if not art.path.endswith(".instructions.md"):
        rep.fail(art.path, "precisa terminar em .instructions.md")
    return body


def check_copilot_agent(rep, art, text, team, agent):
    fm, body = _fm(rep, art.path, text)
    if fm is None:
        return None
    _unknown(rep, art.path, fm, COPILOT_AGENT_KEYS)
    _desc(rep, art.path, fm)
    tools = fm.get("tools", ["*"])
    if not isinstance(tools, list):
        rep.fail(art.path, "tools deve ser lista")
        tools = []
    bad = [t for t in tools if t.lower() not in P.COPILOT_ALIASES and t != "*" and "/" not in t]
    if bad:
        rep.fail(art.path, "tools fora dos aliases do Copilot: %s" % bad)
    if agent and agent["kind"] == "gate" and ("edit" in [t.lower() for t in tools] or "*" in tools):
        rep.fail(art.path, "gate com ferramenta edit")
    if len(body) > COPILOT_MAX_CHARS:
        rep.fail(art.path, "prompt com %d caracteres (máx %d)" % (len(body), COPILOT_MAX_CHARS))
    if not art.path.endswith(".agent.md"):
        rep.fail(art.path, "agente do Copilot precisa terminar em .agent.md")
    return body


def check_codex_agent(rep, art, text, team, agent):
    try:
        data = parse_toml(text)
    except Exception as exc:  # tomllib.TOMLDecodeError ou ValueError do parser mínimo
        rep.fail(art.path, "TOML inválido: %s" % exc)
        return None
    for key in ("name", "description", "developer_instructions"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            rep.fail(art.path, "campo obrigatório ausente: %s" % key)
    if isinstance(data.get("description"), str) and len(data["description"]) > MAX_DESC:
        rep.fail(art.path, "description com %d caracteres (máx %d)" % (len(data["description"]), MAX_DESC))
    if data.get("name") != Path(art.path).stem:
        rep.fail(art.path, "name difere do nome do arquivo")
    sb = data.get("sandbox_mode")
    if sb is not None and sb not in CODEX_SANDBOX:
        rep.fail(art.path, "sandbox_mode inválido: %r" % sb)
    if agent and agent["kind"] == "gate" and sb != "read-only":
        rep.fail(art.path, "gate precisa de sandbox_mode = \"read-only\"")
    return data.get("developer_instructions", "")


CHECKERS = {
    "claude.agent": check_claude_agent, "claude.rule": check_claude_rule, "claude.skill": check_claude_skill,
    "claude.session": check_claude_skill, "claude.command": check_claude_skill,
    "claude.state": check_claude_skill,
    "claude.orchestrator": check_plain,
    "cursor.rule.core": check_cursor_rule, "cursor.rule.orchestrator": check_cursor_rule,
    "cursor.rule.territory": check_cursor_rule, "cursor.agent": check_cursor_agent,
    "copilot.instructions.path": check_copilot_path, "copilot.agent": check_copilot_agent,
    "codex.agent": check_codex_agent,
    "cursor.skill": check_portable_skill, "copilot.skill": check_portable_skill, "codex.skill": check_portable_skill,
    "shared.playbooks": check_json5, "shared.territory": check_json5,
    "maps.tree": check_json5, "maps.stack": check_json5, "maps.s5-memoria": check_json5,
    "maps.invariants": check_json5,
}


def _check_block(rep, art, text):
    try:
        span = find_block(text)
    except ValueError as exc:
        rep.fail(art.path, str(exc))
        return None
    if span is None:
        rep.fail(art.path, "bloco gerenciado ausente (marcadores begin/end)")
        return None
    inner = block_inner(text)
    if inner != art.content.strip("\n"):
        rep.fail(art.path, "bloco gerenciado desatualizado ou editado à mão (rode `cs.py emit`)")
    if art.kind.startswith("codex.agents_md") and len(text.encode("utf-8")) > CODEX_MAX_BYTES:
        rep.fail(art.path, "AGENTS.md com %d bytes > project_doc_max_bytes padrão (32 KiB)" % len(text.encode()))
    return inner


def _layer_text(art, inner):
    """S0 do bloco (sem o kernel, que tem orçamento próprio)."""
    if art.layer == "S0" and "# Orquestrador — kernel" in inner:
        s0, kernel = inner.split("# Orquestrador — kernel", 1)
        return [("S0", s0), ("ORCH", "# Orquestrador — kernel" + kernel)]
    return [(art.layer, inner)]


def validate(root, platforms):
    rep = Report()
    team = load_team(root)
    kn = knowledge.load(root)
    resolve_invariants(team, kn.facts)
    try:
        arts = P.build(team, kn, root, platforms)
    except render.BudgetError as exc:
        rep.fail("team.json", str(exc))
        return rep
    agents = {a["name"]: a for a in team["agents"]}
    for art in arts:
        rep.checked += 1
        dest = Path(root) / art.path
        if not dest.is_file():
            rep.fail(art.path, "ausente (rode `cs.py emit`)")
            continue
        text = read_text(dest)
        agent = agents.get(art.agent)
        if art.mode == P.BLOCK:
            inner = _check_block(rep, art, text)
            if inner is not None:
                for layer, chunk in _layer_text(art, inner):
                    _budget(rep, art.path, layer, chunk)
            continue
        if GEN_TOKEN not in text:
            rep.fail(art.path, "sem marcador de gerado (arquivo humano no caminho de um artefato)")
            continue
        if text != art.content:
            rep.fail(art.path, "desatualizado ou editado à mão (rode `cs.py emit`)")
        body = CHECKERS[art.kind](rep, art, text, team, agent)
        if body is not None:
            _budget(rep, art.path, art.layer, body)
            _gate_verdicts(rep, art.path, team, agent, body)
    _, data = maps.build(root, team)
    for e in maps.check_maps(root, data):
        rep.fail("maps", e)
    _orphans(rep, root, arts, platforms)
    return rep


def _orphans(rep, root, arts, platforms):
    expected = {a.path for a in arts}
    governed = P.manifest_platforms(platforms)
    prefixes = {"claude-code": (".claude/",), "cursor": (".cursor/",), "copilot": (".github/",),
                "codex": (".codex/", ".agents/"), P.SHARED: (".swarm/playbooks", ".swarm/territories"),
                P.MAPS: (".swarm/knowledge",)}
    roots = [d for d in GEN_DIRS if any(d.startswith(p) for g in governed for p in prefixes.get(g, ()))]
    for d in roots:
        base = Path(root) / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.is_symlink():
                continue
            rel = f.relative_to(root).as_posix()
            if rel in expected:
                continue
            try:
                head = f.read_bytes()[:4096].decode("utf-8", "replace")
            except OSError:
                continue
            if GEN_TOKEN in head:
                rep.fail(rel, "órfão: gerado por emissão anterior e sem agente correspondente (rode `cs.py emit`)")
