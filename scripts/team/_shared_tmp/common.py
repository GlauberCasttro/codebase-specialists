"""Raiz do alvo, escrita atômica restrita a .swarm/, globs e classificação de paths.

Espelha cslib.paths/cslib.jsonio (mesma semântica de glob: ** cruza diretórios, * e ? não).
"""
import json
import os
import re
import subprocess
import tempfile

from cslib.paths import STATE_DIR


class CsError(Exception):
    def __init__(self, message, hint=None, code=2):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.code = code

    def render(self):
        out = "erro: " + self.message
        if self.hint:
            out += "\n  como resolver: " + self.hint
        return out


SPECIALISTS = STATE_DIR
RESERVED_PREFIXES = (".swarm/", ".claude/", ".cursor/", ".codex/", ".github/agents/",
                     ".github/instructions/", "scripts/harness/", ".git/")
RESERVED_FILES = ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md")
VENDOR_DIRS = frozenset(["vendor", "node_modules", "third_party", "third-party", "bower_components",
                         ".venv", "venv", "site-packages", "Pods", ".yarn"])
FIXTURE_DIRS = frozenset(["fixtures", "fixture", "__fixtures__", "testdata", "test-data", "test_data",
                          "golden", "goldens", "__snapshots__"])
# examples/ samples/ fora de pasta de teste = exemplo de uso (categoria `example`, mesma regra de cslib.paths):
# fora da análise/stack, mas PODE ter dono (iteração 3: cliente de parceiro em examples/** ficava sem dono)
EXAMPLE_DIRS = frozenset(["examples", "example", "samples", "sample"])
TEST_DIRS = frozenset(["tests", "test", "__tests__", "spec", "specs"])
GENERATED_DIRS = frozenset(["dist", "__pycache__", ".next", ".nuxt", "coverage", ".tox", "generated",
                            "__generated__", ".mypy_cache", ".pytest_cache", ".ruff_cache"])
IGNORED_CLASSES = frozenset(["fixture", "vendor", "generated"])
VEREDITO_ENUM = ["PASS", "FAIL", "NEEDS_SPECIALIST"]
VERDICT_LIKE = re.compile(
    r"\b(PASS|FAIL|NEEDS_[A-Z_]+|APPROVED?|REJECT(?:ED)?|BLOCK(?:ED)?|LGTM|NO[-_]GO|GO)\b")


# ---------------------------------------------------------------- raiz e escrita
def resolve_target(arg=None):
    raw = arg or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = os.path.realpath(os.path.expanduser(raw))
    if not os.path.isdir(root):
        raise CsError("alvo não é um diretório: %s" % raw, "passe --target <repo>")
    return root


def sp_path(target, *parts):
    return os.path.join(target, SPECIALISTS, *parts)


def _ensure_inside(target, path):
    sp = os.path.realpath(sp_path(target))
    parent = os.path.realpath(os.path.dirname(os.path.abspath(path)))
    full = os.path.join(parent, os.path.basename(path))
    if os.path.islink(full):
        raise CsError("recusa escrever em symlink: %s" % full)
    if not (full == sp or full.startswith(sp + os.sep)):
        raise CsError("escrita fora de .swarm/ recusada: %s" % path,
                      "bug do chamador: a skill só escreve em <alvo>/.swarm/")
    return full


try:  # API do ARCHITECTURE §8-decies; fallback local até cslib.json5io existir
    from cslib import json5io as _J5
except ImportError:  # pragma: no cover - depende da integração
    _J5 = None
from team._shared_tmp import json5mini as _J5MINI


def loads5(text):
    if _J5 is not None and hasattr(_J5, "loads"):
        return _J5.loads(text)
    return _J5MINI.loads(text)


def dumps(obj, comment=None):
    """JSON5 determinístico (chaves ordenadas) com comentário de 1 linha no topo."""
    if _J5 is not None and hasattr(_J5, "dumps"):
        try:
            out = _J5.dumps(obj, comment=comment)
        except TypeError:
            out = _J5.dumps(obj)
            if comment and not out.lstrip().startswith("//"):
                out = "// %s\n%s" % (" ".join(comment.split()), out)
        return out if out.endswith("\n") else out + "\n"
    return _J5MINI.dumps(obj, comment)


def find_doc(path):
    """Prefere <x>.json5; aceita <x>.json como fallback de leitura (JSON ⊂ JSON5)."""
    if os.path.isfile(path):
        return path
    if path.endswith(".json5") and os.path.isfile(path[:-1]):
        return path[:-1]
    if path.endswith(".json") and os.path.isfile(path + "5"):
        return path + "5"
    return path


def write_json(target, path, obj, comment=None):
    """Escrita atômica e determinística (JSON5); só dentro de <target>/.swarm/."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    full = _ensure_inside(target, path)
    if comment is None:
        comment = "%s — gerado por codebase-specialists (não editar à mão)" % os.path.basename(path)
    data = dumps(obj, comment).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(full))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, full)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return full


def read_json(path, what=None):
    """Lê JSON5 (ou JSON, subconjunto). Nunca json.load em .json5."""
    path = find_doc(path)
    if not os.path.isfile(path):
        raise CsError("%s ausente: %s" % (what or "arquivo", path))
    try:
        with open(path, "rb") as fh:
            return loads5(fh.read().decode("utf-8"))
    except ValueError as exc:
        raise CsError("%s ilegível (%s): %s" % (what or "JSON", exc, path))


# ---------------------------------------------------------------- classificação
def is_reserved(rel):
    r = rel[2:] if rel.startswith("./") else rel
    if r in RESERVED_FILES:
        return True
    return any(r == p.rstrip("/") or r.startswith(p) for p in RESERVED_PREFIXES)


def path_class(rel):
    dirs = rel.split("/")[:-1]
    if any(d in VENDOR_DIRS for d in dirs):
        return "vendor"
    if any(d in FIXTURE_DIRS for d in dirs):
        return "fixture"
    ex = next((i for i, d in enumerate(dirs) if d in EXAMPLE_DIRS), None)
    if ex is not None:
        return "fixture" if any(d in TEST_DIRS for d in dirs[:ex]) else "example"
    if any(d in GENERATED_DIRS for d in dirs) or re.search(r"\.min\.(js|css)$|_pb2\.py$|\.pb\.go$", rel):
        return "generated"
    if is_reserved(rel):
        return "reserved"
    return "product"


# ---------------------------------------------------------------- globs
_CACHE = {}


def glob_to_regex(pattern):
    p = pattern[2:] if pattern.startswith("./") else pattern
    i, out = 0, []
    while i < len(p):
        c = p[i]
        if c == "*":
            if p[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if p[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_match(rel, pattern):
    rx = _CACHE.get(pattern)
    if rx is None:
        rx = _CACHE[pattern] = glob_to_regex(pattern)
    return bool(rx.match(rel))


def expand(patterns, files):
    pats = [p for p in (patterns or []) if isinstance(p, str) and p]
    return sorted(f for f in files if any(glob_match(f, p) for p in pats))


def has_glob(s):
    return any(c in s for c in "*?")


def compress(owner_of, all_files):
    """owner_of: {path: owner}. all_files: todos os paths que forçam fronteira (owners + reservados).

    Devolve {owner: [globs]} DISJUNTOS por construção: dir/** quando a subárvore inteira (incluindo
    arquivos sem dono reservados, marcados com owner "__reserved__") é de um só dono; senão desce.
    Arquivos ignorados (fixture/vendor/generated) não entram em all_files e não forçam fronteira.
    """
    tree = {}
    for f in all_files:
        node = tree
        parts = f.split("/")
        for d in parts[:-1]:
            node = node.setdefault(d + "/", {})
        node.setdefault("", []).append(f)
    out = {}

    def owners_under(node):
        s = set()
        for k, v in node.items():
            if k == "":
                s.update(owner_of.get(f, "__none__") for f in v)
            else:
                s |= owners_under(v)
        return s

    def emit(o, pat):
        if o in ("__reserved__", "__none__"):
            return
        out.setdefault(o, []).append(pat)

    def rec(node, prefix):
        owners = owners_under(node)
        if prefix and len(owners) == 1:
            emit(next(iter(owners)), prefix + "**")
            return
        direct = sorted(node.get("", []))
        by = {}
        for f in direct:
            by.setdefault(owner_of.get(f, "__none__"), []).append(f)
        if prefix and len(by) == 1 and len(direct) >= 1:  # dir/* cobre arquivo novo direto no dir
            emit(next(iter(by)), prefix + "*")
        else:
            for f in direct:
                emit(owner_of.get(f, "__none__"), f)
        for k in sorted(x for x in node if x):
            rec(node[k], prefix + k)

    rec(tree, "")
    return {k: sorted(v) for k, v in out.items()}


def list_repo_files(root):
    """git ls-files; sem git, os.walk (pulando .git). Sempre POSIX relativo e ordenado."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=60)
        if r.returncode == 0 and r.stdout:
            return sorted(x for x in r.stdout.decode("utf-8", "replace").split("\0") if x)
    except (OSError, subprocess.SubprocessError):
        pass
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d != ".git")
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return sorted(out)


def read_lines(root, rel, cap=2_000_000):
    full = os.path.realpath(os.path.join(root, rel))
    rr = os.path.realpath(root)
    if not full.startswith(rr + os.sep) or not os.path.isfile(full):
        return None
    try:
        with open(full, "rb") as fh:
            data = fh.read(cap)
    except OSError:
        return None
    return data.decode("utf-8", "replace").splitlines()


def norm_cmd(s):
    s = (s or "").strip().strip("`").strip()
    if s.startswith("$ "):
        s = s[2:]
    return re.sub(r"\s+", " ", s).strip()


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "x"
