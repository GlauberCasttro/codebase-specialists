"""Carrega e valida .swarm/team.json para emissão (subconjunto do schema que o emissor exige).

A validação completa (existência de paths, disjunção real de territórios, anti-cola) é do
scripts/probes/check.py; aqui falhamos alto em tudo que tornaria um artefato emitido inválido.
"""
import re
from pathlib import Path
from cslib.paths import STATE_DIR

from emit.common import DEFAULT_VEREDITO, EmitError, WRITE_TOOLS, ALL_PLATFORMS

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
KINDS = ("dev", "gate", "design", "product", "ops")
MAX_DESC = 300
MAX_CORE_LINES = 40
# Tokens que parecem veredito; num gate, todo token assim precisa estar no veredito_enum.
VERDICT_LIKE = re.compile(
    r"\b(PASS|FAIL|NEEDS_[A-Z_]+|APPROVED?|REJECT(?:ED)?|BLOCK(?:ED)?|LGTM|NO[-_]GO|GO)\b")
KNOWN_CLAUDE_TOOLS = {
    "Read", "Grep", "Glob", "Bash", "Edit", "Write", "MultiEdit", "NotebookEdit",
    "WebFetch", "WebSearch", "TodoWrite", "Task", "Agent", "Skill", "TaskGet", "LS",
    "NotebookRead", "BashOutput", "KillShell",
}


def specialists_dir(root):
    return Path(root) / STATE_DIR


TEAM_FILES = ("team.json5", "team.json")  # .json só como transição; .json5 é o formato (§8-decies)


def team_path(root):
    for name in TEAM_FILES:
        p = specialists_dir(root) / name
        if p.is_file():
            return p
    return specialists_dir(root) / TEAM_FILES[0]


def load_team(root):
    from emit import j5
    path = team_path(root)
    if not path.is_file():
        raise EmitError("team.json5 ausente: %s (rode as fases 3–7 antes de emitir)" % path)
    try:
        team = j5.load(path)
    except ValueError as exc:
        raise EmitError("%s ilegível: %s" % (path.name, exc))
    errors = validate_team(team)
    if errors:
        raise EmitError("%s inválido para emissão:\n  - " % path.name + "\n  - ".join(errors))
    return team


def veredito_enum(team):
    enum = team.get("veredito_enum")
    return tuple(enum) if enum else DEFAULT_VEREDITO


def all_card_text(agent):
    card = agent.get("card") or {}
    chunks = [card.get("description", ""), card.get("mission", ""), card.get("done_when", "")]
    for key in ("knows", "refuses", "rules", "footguns"):
        for item in card.get(key) or []:
            chunks.extend([item.get("text", ""), item.get("why", ""), item.get("check", "")])
    for pb in card.get("playbooks") or []:
        chunks.append(pb.get("title", ""))
        chunks.extend(pb.get("steps") or [])
    return "\n".join(c for c in chunks if c)


def foreign_verdicts(text, enum):
    """Tokens com cara de veredito que não pertencem ao enum (ignora `código` entre crases)."""
    plain = re.sub(r"`[^`]*`", " ", text)
    return sorted({t for t in VERDICT_LIKE.findall(plain) if t not in enum})


def validate_team(team):
    errs = []
    if not isinstance(team, dict):
        return ["raiz do team.json não é objeto"]
    if team.get("schema_version") != 1:
        errs.append("schema_version deve ser 1 (achado %r)" % team.get("schema_version"))
    enum = team.get("veredito_enum")
    if not enum or not isinstance(enum, list) or not all(isinstance(x, str) for x in enum):
        errs.append("veredito_enum ausente ou inválido")
        enum = list(DEFAULT_VEREDITO)
    plats = team.get("platforms") or []
    for p in plats:
        if p not in ALL_PLATFORMS:
            errs.append("plataforma desconhecida em platforms: %r" % p)
    core = (team.get("core") or {}).get("lines")
    if not isinstance(core, list) or not core:
        errs.append("core.lines ausente ou vazio")
    else:
        if len(core) > MAX_CORE_LINES:
            errs.append("core.lines tem %d linhas (máx %d)" % (len(core), MAX_CORE_LINES))
        for i, line in enumerate(core):
            if not isinstance(line, dict) or not str(line.get("text", "")).strip():
                errs.append("core.lines[%d] sem text" % i)
            elif "\n" in line["text"]:
                errs.append("core.lines[%d] contém quebra de linha" % i)
    agents = team.get("agents")
    if not isinstance(agents, list) or not agents:
        errs.append("agents ausente ou vazio")
        return errs
    seen = set()
    for i, ag in enumerate(agents):
        where = "agents[%d]" % i
        if not isinstance(ag, dict):
            errs.append("%s não é objeto" % where)
            continue
        name = ag.get("name", "")
        where = "agente %r" % name
        if not isinstance(name, str) or not NAME_RE.match(name):
            errs.append("%s: name fora de ^[a-z][a-z0-9-]{1,40}$" % where)
        if name in seen:
            errs.append("%s: name duplicado" % where)
        seen.add(name)
        kind = ag.get("kind")
        if kind not in KINDS:
            errs.append("%s: kind %r ∉ %s" % (where, kind, list(KINDS)))
        tools = ag.get("tools")
        if not isinstance(tools, list) or not tools or not all(isinstance(t, str) for t in tools):
            errs.append("%s: tools ausente ou não é lista de strings" % where)
            tools = []
        unknown = [t for t in tools if t not in KNOWN_CLAUDE_TOOLS and not t.startswith("mcp__")]
        if unknown:
            errs.append("%s: tools desconhecidas %s" % (where, unknown))
        for key in ("territory", "reads"):
            val = ag.get(key, [])
            if not isinstance(val, list) or not all(isinstance(g, str) and g.strip() for g in val):
                errs.append("%s: %s deve ser lista de globs" % (where, key))
        card = ag.get("card")
        if not isinstance(card, dict):
            errs.append("%s: card ausente" % where)
            continue
        desc = card.get("description", "")
        if not isinstance(desc, str) or not desc.strip():
            errs.append("%s: card.description vazia" % where)
        elif len(desc) > MAX_DESC:
            errs.append("%s: card.description tem %d caracteres (máx %d)" % (where, len(desc), MAX_DESC))
        if not str(card.get("mission", "")).strip():
            errs.append("%s: card.mission vazia" % where)
        if not str(card.get("done_when", "")).strip():
            errs.append("%s: card.done_when vazio" % where)
        for r in card.get("refuses") or []:
            if not str(r.get("why", "")).strip():
                errs.append("%s: recusa sem porquê: %r" % (where, r.get("text")))
        for key in ("knows", "refuses", "rules", "footguns"):
            for item in card.get(key) or []:
                if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                    errs.append("%s: item de %s sem text" % (where, key))
        for pb in card.get("playbooks") or []:
            if not str(pb.get("title", "")).strip() or not pb.get("steps"):
                errs.append("%s: playbook sem título ou passos" % where)
        if kind == "gate":
            bad = [t for t in tools if t in WRITE_TOOLS]
            if bad:
                errs.append("%s: gate com ferramentas de escrita %s" % (where, bad))
            if ag.get("territory"):
                errs.append("%s: gate não tem território de escrita" % where)
            fv = foreign_verdicts(all_card_text(ag), enum)
            if fv:
                errs.append("%s: veredito(s) fora do veredito_enum: %s" % (where, fv))
        elif kind == "dev" and not ag.get("territory") and set(ag.get("tools") or []) & {"Edit", "Write", "MultiEdit"}:
            # qa sem diretório de teste de topo (teste co-localizado é do dono do diretório) fica só-leitura
            errs.append("%s: dev sem território de escrita mas com ferramenta de escrita" % where)
    return errs


def resolve_invariants(team, facts):
    """facts: id -> claim (emit.knowledge)."""
    """Garante que todo invariante citado tem texto; ausência é erro explícito."""
    missing = []
    for ag in team["agents"]:
        for fid in ag.get("invariants") or []:
            if fid not in facts:
                missing.append("%s → %s" % (ag["name"], fid))
    if missing:
        raise EmitError("invariantes sem fato em .swarm/facts/: " + ", ".join(missing))
