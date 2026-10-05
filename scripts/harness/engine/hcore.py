"""hcore — primitivas do harness (copiado para <alvo>/<STATE_DIR>/harness/).

Fonte única de: carga das máquinas (machines.json5), enum de veredito, cadeia de hashes, escrita
atômica, raiz, globs, operações de evento (create/set/append/inc) e checagem de legalidade das mudanças
de estado. engine/state/validate/guard importam daqui. Python 3.9+ stdlib.
"""
import contextlib
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone

import j5

HERE = os.path.dirname(os.path.abspath(__file__))
# Espelho de cslib.paths.STATE_DIR/LEGACY_STATE_DIR (o motor é copiado ao alvo sem o cslib).
STATE_DIR = ".swarm"
# Nome legado MONTADO (o motor copiado ao alvo não carrega o literal): só detecção (sonda de harness único) e
# migração; nunca escrito.
LEGACY_STATE_DIR = "." + "specialists"
SCHEMA_VERSION = 2
GENESIS = "0" * 64
KINDS = ("session", "epic", "feature", "sprint", "story", "task", "deleg", "consult")
BOARD_LISTS = {"session": "sessions", "epic": "epics", "feature": "features", "sprint": "sprints",
               "story": "stories", "task": "tasks", "consult": "consults"}
KIND_MACHINE = {"session": "session", "epic": "epic", "feature": "feature", "sprint": "sprint",
                "story": "story", "task": "task", "deleg": "delegation", "consult": "consult"}
# listas acrescentadas depois do schema 2: board antigo sem elas é lido como lista vazia (compatível).
OPTIONAL_LISTS = ("consults",)

# Nunca entram em território de produto; casamento por PREFIXO de path relativo (lição §8).
RESERVED_PREFIXES = (STATE_DIR + "/", LEGACY_STATE_DIR + "/", ".claude/", ".git/", ".cursor/", ".codex/",
                     ".github/agents/",
                     ".github/instructions/", "scripts/harness/")


class StateError(Exception):
    """Estado ausente/ilegível/incoerente. Sempre fail-closed."""


class Refused(Exception):
    """Transição recusada por guarda. .problems = lista de mensagens acionáveis."""

    def __init__(self, problems, hint=None):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        self.hint = hint
        Exception.__init__(self, "; ".join(self.problems))

    def render(self):
        s = "RECUSADO:\n" + "\n".join("  - " + p for p in self.problems)
        if self.hint:
            s += "\n  → " + self.hint
        return s


# ---------------------------------------------------------------- máquinas
_MACHINES = None


def machines_path():
    for cand in (os.path.join(HERE, "machines.json5"), os.path.join(os.path.dirname(HERE), "machines.json5")):
        if os.path.isfile(cand):
            return cand
    raise StateError("machines.json5 ausente ao lado do motor (fail-closed)")


def machines():
    global _MACHINES
    if _MACHINES is None:
        _MACHINES = j5.load(machines_path())
    return _MACHINES


def verdicts():
    return tuple(machines()["verdict_enum"])


def legal_pairs(machine_name):
    m = machines()["machines"][machine_name]
    pairs = set(tuple(p) for p in m.get("pairs") or [])
    for t in (m.get("transitions") or {}).values():
        tos = [t["to"]] + list(t.get("alt_to") or [])
        for f in t["from"]:
            for to in tos:
                pairs.add((f, f if to == "=" else to))
    for p in m.get("extra_pairs") or []:
        pairs.add(tuple(p))
    return pairs


def state_field(kind):
    return machines()["machines"][KIND_MACHINE[kind]].get("field", "state")


# ---------------------------------------------------------------- raiz e paths
def resolve_root(arg=None):
    """Raiz = argumento explícito ou CLAUDE_PROJECT_DIR (ou CS_ROOT). NUNCA o diretório do script."""
    root = arg or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CS_ROOT")
    if not root:
        raise StateError("raiz do projeto indefinida: passe --root ou defina CLAUDE_PROJECT_DIR")
    root = os.path.realpath(os.path.abspath(root))
    if not os.path.isdir(root):
        raise StateError("raiz inexistente: %s" % root)
    return root


TREE_ZONES = ("backlog", "state", "archive")
TREE_RUNTIME = ".engine"  # projeção do motor (o antigo board), lock, ledgers e evidências no modo árvore
# Modo árvore: só o motor escreve nas zonas, na cadeia e na projeção (guard bloqueia Write/Edit/Bash do modelo).
TREE_PROTECTED = tuple("%s/%s/" % (STATE_DIR, z) for z in TREE_ZONES) + (
    STATE_DIR + "/events.jsonl", STATE_DIR + "/INDEX.md", "%s/%s/" % (STATE_DIR, TREE_RUNTIME))


def tree_mode(root):
    """Estado em árvore de pastas (backlog/ state/ archive/ + <STATE_DIR>/events.jsonl na raiz)."""
    return os.path.isfile(os.path.join(root, STATE_DIR, "events.jsonl"))


def tree_paths(root):
    sp = os.path.join(root, STATE_DIR)
    rt = os.path.join(sp, TREE_RUNTIME)
    return {
        "specialists": sp, "state_dir": rt, "zones": sp,
        "board": os.path.join(rt, "projection.json5"),
        "events": os.path.join(sp, "events.jsonl"),
        "index": os.path.join(sp, "INDEX.md"),
        "ledger": os.path.join(rt, "harness-ledger.jsonl"),
        "autonomy": os.path.join(rt, "autonomy.json5"),
        "lock": os.path.join(rt, ".lock"),
        "evidence": os.path.join(rt, "evidence"),
        "selftest": os.path.join(rt, "selftest.json5"),
        "config": os.path.join(sp, "harness", "config.json5"),
        "team": os.path.join(sp, "team.json5"),
        "facts_dir": os.path.join(sp, "facts"),
        "knowledge_dir": os.path.join(sp, "knowledge"),
        "session_dir": os.path.join(sp, "session"),
        "run": os.path.join(sp, "run.json5"),
        "tree": True,
    }


def state_paths(root):
    if tree_mode(root):
        return tree_paths(root)
    sp = os.path.join(root, STATE_DIR)
    sd = os.path.join(sp, "state")
    return {
        "specialists": sp, "state_dir": sd,
        "board": os.path.join(sd, "board.json5"),
        "events": os.path.join(sd, "events.jsonl"),
        "ledger": os.path.join(sd, "harness-ledger.jsonl"),  # encadeado; ledger.jsonl é o log do cs.py (cslib.log)
        "autonomy": os.path.join(sd, "autonomy.json5"),
        "lock": os.path.join(sd, ".lock"),
        "evidence": os.path.join(sd, "evidence"),
        "selftest": os.path.join(sd, "selftest.json5"),
        "config": os.path.join(sp, "harness", "config.json5"),
        "team": os.path.join(sp, "team.json5"),
        "facts_dir": os.path.join(sp, "facts"),
        "knowledge_dir": os.path.join(sp, "knowledge"),
        "session_dir": os.path.join(sp, "session"),
        "run": os.path.join(sp, "run.json5"),
    }


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path, data):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_json5(path, obj, header):
    atomic_write_bytes(path, j5.dumps(obj, header=header).encode("utf-8"))


def read_any(path):
    """Lê .json5 (j5) ou .json (json estrito). Nunca json.load em .json5."""
    if path.endswith(".json5"):
        return j5.load(path)
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def foreign_harness_signals(root):
    """Sinais de OUTRO harness (ou do diretório legado desta skill) no alvo: [(rel, motivo)].

    Harness único: o harness desta skill vive só em <alvo>/<STATE_DIR>/ + .claude/hooks/cs-guard.sh. Cada sinal
    sozinho basta: placa v8 (<STATE_DIR>/instance.json), scripts/harness/, .claude/kernel/, hook do
    .claude/settings.json que roda um script de .claude/hooks/ que não é cs-guard.sh, e o diretório legado
    (LEGACY_STATE_DIR). Um comando avulso do usuário (ex.: `mine.sh`, preservado pelo merge do install) não é
    harness."""
    out = []
    if os.path.isfile(os.path.join(root, STATE_DIR, "instance.json")):
        out.append((STATE_DIR + "/instance.json", "placa de outro harness (v8)"))
    if os.path.isdir(os.path.join(root, "scripts", "harness")):
        out.append(("scripts/harness/", "motor de outro harness"))
    if os.path.isdir(os.path.join(root, ".claude", "kernel")):
        out.append((".claude/kernel/", "kernel de outro harness"))
    sp = os.path.join(root, ".claude", "settings.json")
    if os.path.isfile(sp):
        try:
            with open(sp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        hooks = data.get("hooks") if isinstance(data, dict) else None
        for ev, groups in (hooks or {}).items() if isinstance(hooks, dict) else ():
            for g in groups or []:
                for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
                    cmd = (h.get("command") or "") if isinstance(h, dict) else ""
                    if ".claude/hooks/" in cmd and "cs-guard.sh" not in cmd:
                        out.append((".claude/settings.json", "hook %s de terceiros: %s" % (ev, cmd[:80])))
    if os.path.lexists(os.path.join(root, LEGACY_STATE_DIR)):
        out.append((LEGACY_STATE_DIR + "/", "diretório legado desta skill (rode `cs.py upgrade`)"))
    return out


def first_existing(*paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


_HELD = {}


@contextlib.contextmanager
def file_lock(lock_path):
    """flock exclusivo, REENTRANTE no mesmo processo (guardas que gravam ledger dentro de um commit)."""
    key = os.path.realpath(lock_path)
    if _HELD.get(key):
        _HELD[key] += 1
        try:
            yield
        finally:
            _HELD[key] -= 1
        return
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    f = open(lock_path, "a+")
    try:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except ImportError:  # Windows: sem flock; passos que escrevem rodam em série
            pass
        _HELD[key] = 1
        yield
    finally:
        _HELD.pop(key, None)
        f.close()


# ---------------------------------------------------------------- cadeia de hashes (JSONL estrito)
def _read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        data = f.read()
    return [ln for ln in data.split(b"\n") if ln.strip()]


def last_hash(path):
    lines = _read_lines(path)
    return sha256_bytes(lines[-1]) if lines else GENESIS


def append_chained(path, record):
    """Anexa record com prev = sha256(bytes da linha anterior). Retorna (hash_da_linha, seq). Chamador segura o lock."""
    lines = _read_lines(path)
    rec = dict(record)
    rec["seq"] = len(lines)
    rec["prev"] = sha256_bytes(lines[-1]) if lines else GENESIS
    line = canonical(rec).encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "ab") as f:
        f.write(line + b"\n")
        f.flush()
        os.fsync(f.fileno())
    return sha256_bytes(line), rec["seq"]


def read_chain(path):
    """(records, errors, last_hash). Confere prev e seq de cada linha."""
    errors, records = [], []
    prev = GENESIS
    for i, raw in enumerate(_read_lines(path)):
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            errors.append("linha %d: JSON inválido (%s)" % (i, e))
            prev = sha256_bytes(raw)
            continue
        if not isinstance(rec, dict):
            errors.append("linha %d: não é objeto" % i)
        else:
            if rec.get("prev") != prev:
                errors.append("linha %d: cadeia quebrada (prev=%s esperado=%s)" % (i, str(rec.get("prev"))[:12], prev[:12]))
            if rec.get("seq") != i:
                errors.append("linha %d: seq=%r fora de ordem" % (i, rec.get("seq")))
            records.append(rec)
        prev = sha256_bytes(raw)
    return records, errors, prev


def ledger_append(root, entry):
    """Grava no ledger (bloqueios, kill-switch). Levanta exceção se não conseguir gravar."""
    p = state_paths(root)
    rec = {"at": now_iso()}
    rec.update(entry)
    with file_lock(p["lock"]):
        return append_chained(p["ledger"], rec)


# ---------------------------------------------------------------- paths / globs
def norm_rel(p):
    if not isinstance(p, str) or not p.strip():
        raise StateError("path vazio")
    p = p.strip().replace("\\", "/")
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p):
        raise StateError("path absoluto não permitido: %s" % p)
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if ".." in parts:
        raise StateError("'..' não permitido: %s" % p)
    out = "/".join(parts)
    if p.endswith("/") and out:
        out += "/"
    return out


_GLOB_CACHE = {}


def glob_to_re(pat):
    if pat in _GLOB_CACHE:
        return _GLOB_CACHE[pat]
    i, out = 0, []
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    rx = re.compile("^" + "".join(out) + "$")
    _GLOB_CACHE[pat] = rx
    return rx


def has_wild(p):
    return any(ch in p for ch in "*?[")


def path_matches(rel, pattern):
    """rel casa com pattern? 'dir/' ou 'dir' sem curinga = prefixo de diretório; 'a/b.py' = arquivo."""
    pattern = norm_rel(pattern)
    if pattern in ("**", "**/"):
        return True
    if has_wild(pattern):
        return bool(glob_to_re(pattern.rstrip("/")).match(rel))
    pat = pattern.rstrip("/")
    return rel == pat or rel.startswith(pat + "/")


def matches_any(rel, patterns):
    return any(path_matches(rel, p) for p in patterns or [])


def literal_prefix(pattern):
    """Prefixo literal de um glob até o último '/' antes do primeiro curinga ('' = raiz inteira)."""
    if pattern in ("", "**", "**/*", "*", "**/"):
        return ""
    pattern = norm_rel(pattern)
    if not has_wild(pattern):
        return pattern.rstrip("/") + "/"
    cut = min(pattern.index(ch) for ch in "*?[" if ch in pattern)
    head = pattern[:cut]
    return head[: head.rfind("/") + 1]


def scopes_overlap(scopes_a, scopes_b):
    """Conservador (super-inclui): dois conjuntos de globs se tocam se um prefixo literal contém o outro."""
    for a in scopes_a or []:
        pa = literal_prefix(a)
        for b in scopes_b or []:
            pb = literal_prefix(b)
            if pa.startswith(pb) or pb.startswith(pa):
                return True
    return False


def is_global_scope(scopes):
    return not scopes or any(literal_prefix(s) == "" for s in scopes)


def pattern_within(pattern, territory):
    """pattern ⊆ algum glob do território? Literal: casa por path_matches; glob: prefixo literal contido."""
    if not has_wild(pattern):
        rel = norm_rel(pattern).rstrip("/")
        return any(path_matches(rel, t) for t in territory or [])
    lp = literal_prefix(pattern)
    for t in territory or []:
        tl = literal_prefix(t)
        if lp.startswith(tl) and (not has_wild(t) or t.rstrip("/").endswith("**")):
            return True
        if lp.startswith(tl) and has_wild(t) and glob_to_re(norm_rel(t).rstrip("/")).match(pattern.rstrip("/")):
            return True
    return False


def is_reserved(rel_pattern):
    lp = literal_prefix(rel_pattern)
    if not has_wild(rel_pattern):
        lp = norm_rel(rel_pattern).rstrip("/") + "/"
    return any(lp.startswith(r) for r in RESERVED_PREFIXES)


def resolve_target(root, path, base=None):
    """(lexical_rel|None, real_rel|None). None = fora da raiz. realpath sempre (lição X-01)."""
    root_rp = os.path.realpath(root)
    raw_root = os.path.normpath(os.path.abspath(root))
    base = base or root_rp
    absp = path if os.path.isabs(path) else os.path.join(base, path)
    lex = os.path.normpath(absp)
    real = os.path.realpath(absp)

    def rel(p, r):
        if p == r:
            return ""
        if p.startswith(r + os.sep):
            return os.path.relpath(p, r).replace(os.sep, "/")
        return None
    lex_rel = rel(lex, root_rp)
    if lex_rel is None:
        lex_rel = rel(lex, raw_root)
    return lex_rel, rel(real, root_rp)


# ---------------------------------------------------------------- board e operações
def new_board():
    b = {"schema_version": SCHEMA_VERSION, "event_count": 0, "last_event_hash": GENESIS}
    for lst in BOARD_LISTS.values():
        b[lst] = []
    return b


def load_board(root):
    p = state_paths(root)["board"]
    if not os.path.isfile(p):
        raise StateError("board ausente: %s (estado ausente = bloqueio; rode cs-state init)" % p)
    try:
        b = j5.load(p)
    except (OSError, ValueError) as e:
        raise StateError("board ilegível: %s" % e)
    if not isinstance(b, dict) or b.get("schema_version") != SCHEMA_VERSION:
        raise StateError("board com schema inválido (schema_version != %d)" % SCHEMA_VERSION)
    for lst in OPTIONAL_LISTS:
        if lst not in b:
            b[lst] = []
    for lst in BOARD_LISTS.values():
        if not isinstance(b.get(lst), list):
            raise StateError("board sem lista %s" % lst)
    return b


def save_board(root, board):
    write_json5(state_paths(root)["board"], board,
                "board.json5 — estado do harness; escrito SÓ por cs-state (cadeia em events.jsonl)")


def find(board, kind, eid):
    if kind == "deleg":
        for t in board["tasks"]:
            for d in t.get("delegations") or []:
                if d.get("id") == eid:
                    return d
        return None
    for e in board[BOARD_LISTS[kind]]:
        if e.get("id") == eid:
            return e
    return None


def task_of_deleg(board, did):
    for t in board["tasks"]:
        for d in t.get("delegations") or []:
            if d.get("id") == did:
                return t
    return None


def kind_of(board, eid):
    for k in ("task", "story", "feature", "epic", "sprint", "session", "deleg", "consult"):
        if find(board, k, eid) is not None:
            return k
    return None


def apply_ops(board, ops, check_legal=True, legacy=None, on_illegal=None):
    """Aplica operações de um evento. Mudança no campo de estado é checada contra machines.json5.
    legacy: {(ref, de, para)} reconhecidos por um evento harness.legacy_ack (histórico de motor antigo/hotfix).
    on_illegal(ref, de, para): em vez de abortar, registra e segue (usado só para LISTAR o histórico ilegal)."""
    for op in ops:
        kind = op[0]
        if kind in ("tput", "tdel", "tmeta"):
            # modo árvore: itens (épico/sprint/feature/story/task) por id; tmeta = contadores (ids nunca reaproveitados)
            if kind == "tput":
                board.setdefault("tree", {})[op[1]] = json.loads(json.dumps(op[3]))
            elif kind == "tdel":
                if op[1] not in board.setdefault("tree", {}):
                    raise StateError("tdel: item inexistente %s" % op[1])
                del board["tree"][op[1]]
            else:
                board.setdefault("tree_meta", {})[op[1]] = json.loads(json.dumps(op[3]))
            continue
        if kind == "create":
            _, ek, parent, obj = op
            if ek == "deleg":
                t = find(board, "task", parent)
                if t is None:
                    raise StateError("create deleg: task %s inexistente" % parent)
                if find(board, "deleg", obj["id"]):
                    raise StateError("deleg já existe: %s" % obj["id"])
                t.setdefault("delegations", []).append(json.loads(json.dumps(obj)))
            else:
                if find(board, ek, obj["id"]):
                    raise StateError("%s já existe: %s" % (ek, obj["id"]))
                board[BOARD_LISTS[ek]].append(json.loads(json.dumps(obj)))
            continue
        _, ref, field, value = op
        ek, eid = ref.split(":", 1)
        ent = find(board, ek, eid)
        if ent is None:
            raise StateError("%s: entidade inexistente %s" % (kind, ref))
        if kind == "set":
            if check_legal and field == state_field(ek):
                old = ent.get(field)
                if (old, value) not in legal_pairs(KIND_MACHINE[ek]) and (ref, old, value) not in (legacy or ()):
                    if on_illegal is None:
                        raise StateError("transição ilegal em %s: %s→%s" % (ref, old, value))
                    on_illegal(ref, old, value)
            ent[field] = json.loads(json.dumps(value))
        elif kind == "append":
            ent.setdefault(field, []).append(json.loads(json.dumps(value)))
        elif kind == "inc":
            ent[field] = int(ent.get(field) or 0) + int(value)
        else:
            raise StateError("op desconhecida: %r" % kind)


# ---------------------------------------------------------------- team, config, fatos
def load_team(root):
    p = state_paths(root)
    path = first_existing(p["team"], os.path.join(p["specialists"], "team.json"))
    if not path:
        return None
    try:
        t = read_any(path)
        return t if isinstance(t, dict) else None
    except (OSError, ValueError):
        return None


def team_agent(team, name):
    for a in (team or {}).get("agents") or []:
        if isinstance(a, dict) and a.get("name") == name:
            return a
    return None


def gate_agents(team):
    return {a.get("name") for a in (team or {}).get("agents") or [] if isinstance(a, dict) and a.get("kind") == "gate"}


DEFAULT_CONFIG = {
    "schema_version": 1,
    "lead_write_allow": [STATE_DIR + "/", "docs/state/"],
    "protected": [STATE_DIR + "/state/", STATE_DIR + "/backlog/", STATE_DIR + "/archive/", STATE_DIR + "/events.jsonl",
                  STATE_DIR + "/INDEX.md", STATE_DIR + "/" + TREE_RUNTIME + "/",
                  STATE_DIR + "/harness/", STATE_DIR + "/bin/", STATE_DIR + "/memory/",
                  ".claude/hooks/", ".claude/settings.json", ".claude/settings.local.json", ".git/"],
    "frozen_paths": [],
    "protected_branches": ["main", "master"],
    "readonly_agents": ["Explore", "Plan", "claude-code-guide", "statusline-setup"],
    "verify_timeout_s": 900,
    "post_edit_checks": [],
    "test_runners": [
        {"match": r"^(?P<file>[^:]+\.py)::(?P<name>.+)$", "argv": ["python3", "-m", "pytest", "-q", "{test}"]},
        {"match": r"^(?P<mod>[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)+)$", "argv": ["python3", "-m", "unittest", "{test}"]},
        {"match": r"^cmd:(?P<cmd>.+)$", "shell": True},
    ],
    "regression_command": None,
    "context_budget_chars": 10000,
    "require_git_diff_check": True,
}


def load_config(root):
    p = state_paths(root)["config"]
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.isfile(p):
        user = j5.load(p)  # ilegível ⇒ exceção ⇒ chamador bloqueia
        if not isinstance(user, dict):
            raise StateError("config.json5 não é objeto")
        cfg.update(user)
    return cfg


def load_facts(root):
    """Fatos por id de facts/*.json5|*.json, tolerante ao formato. Cada fato ganha '_file'."""
    d = state_paths(root)["facts_dir"]
    facts = {}

    def take(obj, fname, depth=0):
        if depth > 3:
            return
        if isinstance(obj, list):
            for f in obj:
                if isinstance(f, dict) and isinstance(f.get("id"), str):
                    f = dict(f)
                    f["_file"] = fname
                    facts[f["id"]] = f
                elif isinstance(f, (list, dict)):
                    take(f, fname, depth + 1)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (list, dict)):
                    if isinstance(v, dict) and not isinstance(v.get("id"), str) and ("claim" in v or "scope" in v):
                        v = dict(v)
                        v["id"] = k
                        v["_file"] = fname
                        facts[k] = v
                    else:
                        take(v, fname, depth + 1)
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.endswith(".json5") or name.endswith(".json"):
                try:
                    take(read_any(os.path.join(d, name)), name)
                except (OSError, ValueError):
                    continue
    return facts


def fact_category(f):
    name = f.get("_file", "")
    if name.startswith("glossary"):
        return "term"
    if name.startswith("business_rules"):
        return "business_rule"
    if f.get("layer") in ("rules", "invariants") or name.startswith("rules"):
        return "rule"
    return "fact"


def fact_text(f):
    for k in ("claim", "text", "rule", "statement", "definition", "description", "term", "canonical", "name"):
        if isinstance(f.get(k), str) and f[k].strip():
            return f[k].strip()
    return f.get("id", "")


def fact_scope(f):
    for k in ("scope", "scope_paths", "paths"):
        v = f.get(k)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, str)]
    return [e["file"] for e in f.get("evidence") or [] if isinstance(e, dict) and isinstance(e.get("file"), str)]
