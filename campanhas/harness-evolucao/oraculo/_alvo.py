"""Helpers do oráculo harness-evolucao — alvos de rascunho e CLI REAL do harness do produto.

Nada aqui é mock: o alvo é um repo git temporário (scripts/harness/tests/fixture.py:make_repo da skill testada), o
harness entra por `cs.py harness install` e todo comando roda em subprocesso:
  cs-state = <alvo>/.swarm/harness/state.py --root <alvo>   (o que o wrapper .swarm/bin/cs-state executa)
  cs-mem   = <alvo>/.swarm/harness/mem.py   --root <alvo>   (o que o wrapper .swarm/bin/cs-mem executa)
  guard    = <alvo>/.swarm/harness/guard.py <modo>, payload no stdin, CLAUDE_PROJECT_DIR=<alvo>
Os wrappers .swarm/bin/cs-* são sh e chamam `python3`, que no Windows nativo pode não existir para subprocesso: o
oráculo chama o .py instalado com sys.executable (mesmo código, mesma raiz).

Skill testada: $CS_DEV_SKILL_DIR (padrão: a raiz do projeto, três níveis acima desta pasta). Só stdlib, Python 3.9+.
Comandos de verify/aceite usam o MESMO interpretador (caminho absoluto, entre aspas, com '/'), nunca `python3`.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
import io

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.realpath(os.environ.get("CS_DEV_SKILL_DIR") or PROJ)
SCRIPTS = os.path.join(SKILL, "scripts")
CS_PY = os.path.join(SCRIPTS, "cs.py")
ENGINE_SRC = os.path.join(SCRIPTS, "harness", "engine")
FIXTURE_DIR = os.path.join(SCRIPTS, "harness", "tests")
SD = ".swarm"
# commit da skill 0.10.0 com o estado em JSON5 (HEAD quando o oráculo foi escrito): gera o alvo LEGADO do CA-19
LEGACY_REV = "7aa3cb4917ac80e22173e7c70e64f0a8dcec1ae8"

if FIXTURE_DIR not in sys.path:
    sys.path.insert(0, FIXTURE_DIR)
import fixture  # noqa: E402  (da skill testada; insere engine/ e memory/ no sys.path)

j5 = fixture.j5

PY = sys.executable
PYQ = '"%s"' % PY.replace("\\", "/")
VERIFY = PYQ + " -m unittest discover -s tests -t ."
VERDE = PYQ + " -m unittest tests.test_billing"              # sempre verde
ACEITE = PYQ + " -m unittest accept.test_accept"             # verde só depois de src/billing/discount.py existir
ACEITE_NUNCA = PYQ + " -m unittest accept.test_nunca"        # sempre vermelho (src/billing/nunca.py nunca é criado)
ACEITE_MARCA = PYQ + " -m unittest accept.test_marca"        # verde só se o arquivo $CS_ORACULO_MARCA existir
VERMELHO_3 = PYQ + ' -c "raise SystemExit(3)"'
INEXISTENTE = "cs-oraculo-programa-inexistente-xyz --rodar"
CRIT = "AC-1|Dado pedido Quando aplico Entao o total muda|"
CREATED_RE = re.compile(r"criad[oa] (\S+) em (\S+)")
ZONES = ("backlog", "state", "archive")

EXTRA_FILES = {
    "accept/test_nunca.py": ("import os, unittest\nclass N(unittest.TestCase):\n    def test_nunca(self):\n"
                             "        self.assertTrue(os.path.exists('src/billing/nunca.py'))\n"),
    "accept/test_marca.py": ("import os, unittest\nclass M(unittest.TestCase):\n    def test_marca(self):\n"
                             "        self.assertTrue(os.path.exists(os.environ.get('CS_ORACULO_MARCA') or "
                             "'/cs-oraculo/nao/existe'))\n"),
}


# ====================================================================== processo
def env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE", "CS_MIGRATIONS_FILE"):
        e.pop(k, None)
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    e.update(extra or {})
    return e


def run(argv, cwd=None, inp=None, extra=None, timeout=900):
    p = subprocess.run(argv, cwd=cwd, env=env(extra), input=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


# ====================================================================== leitura
def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "replace")


def read_doc(path):
    """JSON estrito ou JSON5 legado (o leitor do motor)."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return j5.loads(raw)


def read_jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    for line in read_text(path).splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def norm(text):
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def json_fmt_problem(text):
    """None se `text` é JSON válido, indent 2, uma propriedade por linha e '\\n' final (formato do gravador único)."""
    if not text:
        return "vazio"
    if "\r" in text:
        return "tem \\r (CRLF)"
    if not text.endswith("\n"):
        return "sem \\n final"
    try:
        obj = json.loads(text)
    except ValueError as e:
        return "não é JSON (%s)" % e
    for ea in (False, True):
        if json.dumps(obj, indent=2, ensure_ascii=ea) + "\n" == text:
            return None
    return "JSON fora do formato indent 2 / uma propriedade por linha"


def walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for x in walk_dicts(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in walk_dicts(v):
                yield x


def snapshot(root, skip=("backups", "harness", "memory/index", ".engine/.lock", "memory/.lock")):
    """{relpath sob .swarm: sha256} — o que mudou de verdade (fora cache de índice, locks, backups e código)."""
    base = os.path.join(root, SD)
    out = {}
    for dp, dns, fs in os.walk(base):
        r = os.path.relpath(dp, base).replace(os.sep, "/")
        r = "" if r == "." else r
        if any(r == s or r.startswith(s + "/") for s in skip):
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d != "__pycache__"]
        for f in fs:
            rel = (r + "/" + f).lstrip("/")
            if rel in skip or f.endswith(".lock"):
                continue
            out[rel] = sha_file(os.path.join(dp, f))
    return out


def all_files_text(base):
    """Texto concatenado de todos os arquivos sob `base` (para procurar segredo/marcador)."""
    out = []
    if not os.path.isdir(base):
        return ""
    for dp, _, fs in os.walk(base):
        for f in fs:
            try:
                out.append(read_text(os.path.join(dp, f)))
            except OSError:
                pass
    return "\n".join(out)


# ====================================================================== alvo
def make_repo():
    root = fixture.make_repo(with_state=False)
    for rel, txt in EXTRA_FILES.items():
        fixture.write(root, rel, txt)
    fixture.git(root, "add", "-A")
    fixture.git(root, "commit", "-qm", "oraculo: aceites extras")
    return root


class Alvo(object):
    """Um alvo de rascunho com o harness instalado. `skill`: raiz da skill que instala (padrão: a testada)."""

    def __init__(self, root, skill=SKILL):
        self.root = root
        self.skill = skill
        self.extra = {}

    @classmethod
    def novo(cls, install=True, skill=SKILL):
        a = cls(make_repo(), skill)
        if install:
            rc, out, err = a.install()
            if rc != 0:
                raise AssertionError("cs.py harness install falhou (exit %d): %s%s" % (rc, out, err))
        return a

    def rm(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # ---- caminhos
    def p(self, *parts):
        return os.path.join(self.root, SD, *parts)

    def write(self, rel, txt="X = 1\n"):
        fixture.write(self.root, rel, txt)

    # ---- comandos reais
    def install(self, skill=None):
        cs_py = os.path.join(skill or self.skill, "scripts", "cs.py")
        return run([PY, "-B", cs_py, "--target", self.root, "harness", "install", "--platforms", "claude-code",
                    "--allow-outside", "--no-settings"], cwd=self.root)

    def cspy(self, *args, skill=None):
        cs_py = os.path.join(skill or self.skill, "scripts", "cs.py")
        return run([PY, "-B", cs_py, "--target", self.root] + list(args), cwd=self.root)

    def cs(self, *args, actor=None, engine=None):
        """cs-state (instalado no alvo; `engine`: outro state.py, ex. o da skill)."""
        argv = [PY, "-B", engine or self.p("harness", "state.py"), "--root", self.root]
        if actor:
            argv += ["--actor", actor]
        return run(argv + list(args), cwd=self.root, extra=self.extra)

    def mem(self, *args):
        return run([PY, "-B", self.p("harness", "mem.py"), "--root", self.root] + list(args), cwd=self.root,
                   extra=self.extra)

    def hook(self, mode, payload):
        return run([PY, "-B", self.p("harness", "guard.py"), mode], cwd=self.root,
                   inp=json.dumps(payload).encode("utf-8"), extra={"CLAUDE_PROJECT_DIR": self.root})

    # ---- árvore
    def nodes(self):
        rc, out, err = self.cs("tree", "--json")
        if rc != 0:
            raise AssertionError("cs-state tree --json falhou (exit %d): %s%s" % (rc, out, err))
        res = {}

        def walk(ns):
            for n in ns:
                res[n["id"]] = n
                walk(n.get("children") or [])
        for z in ZONES:
            walk(json.loads(out)["zonas"].get(z) or [])
        return res

    def node(self, ident):
        n = self.nodes().get(ident)
        if n is None:
            raise AssertionError("item %s não está na árvore" % ident)
        return n

    def item_path(self, ident):
        return os.path.join(self.root, self.node(ident)["path"])

    def item(self, ident):
        return read_doc(self.item_path(ident))

    def zona(self, ident):
        return self.node(ident)["zona"]

    # ---- memória
    def agent_mem_file(self, agent):
        """Arquivo de memória (lições) do agente: .json (novo) ou .json5 (legado), em state/memory/agents ou
        memory/agents. None se não existe."""
        for d in (self.p("state", "memory", "agents"), self.p("memory", "agents")):
            for ext in (".json", ".json5"):
                f = os.path.join(d, agent + ext)
                if os.path.isfile(f):
                    return f
        return None

    def lessons(self, agent):
        f = self.agent_mem_file(agent)
        if not f:
            return []
        d = read_doc(f)
        return list((d or {}).get("lessons") or []) if isinstance(d, dict) else []

    def knowledge(self):
        return read_jsonl(self.p("memory", "knowledge.jsonl"))

    # ---- eventos (cadeia do motor + ledgers)
    LEDGERS = ("events.jsonl", "harness-ledger.jsonl", "ledger.jsonl", "state/events.jsonl",
               "state/harness-ledger.jsonl", "state/ledger.jsonl")

    def records(self):
        out = []
        for rel in self.LEDGERS:
            for r in read_jsonl(self.p(*rel.split("/"))):
                r = dict(r)
                r["_arquivo"] = rel
                out.append(r)
        return out

    def find_events(self, name):
        """Registros cujo tipo é `name` (ou termina em .name / :name), em qualquer ledger; dados mesclados."""
        hits = []
        for r in self.records():
            for k in ("type", "kind", "event", "acao", "action", "op", "name"):
                v = r.get(k)
                if isinstance(v, str) and (v == name or v.endswith("." + name) or v.endswith(":" + name)):
                    d = dict(r)
                    if isinstance(r.get("data"), dict):
                        d.update(r["data"])
                    hits.append(d)
                    break
        return hits

    def events_bytes(self):
        p = self.p("events.jsonl")
        if not os.path.isfile(p):
            return b""
        with open(p, "rb") as f:
            return f.read()


# ====================================================================== skill legada (CA-19)
_LEGACY = {}


def legacy_skill():
    """Extrai scripts/, references/, assets/ e VERSION do commit LEGACY_REV (skill 0.10.0, estado em JSON5)."""
    d = _LEGACY.get("dir")
    if d and os.path.isdir(d):
        return d
    rc, top, err = run(["git", "rev-parse", "--show-toplevel"], cwd=HERE)
    if rc != 0:
        raise AssertionError("CA-19 precisa do histórico git do projeto para montar o alvo 0.10.0: %s" % err)
    p = subprocess.run(["git", "archive", "--format=zip", LEGACY_REV, "scripts", "references", "assets", "VERSION"],
                       cwd=top.strip(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if p.returncode != 0:
        raise AssertionError("git archive %s falhou: %s" % (LEGACY_REV, p.stderr.decode("utf-8", "replace")))
    d = tempfile.mkdtemp(prefix="cs-skill-0100-")
    with zipfile.ZipFile(io.BytesIO(p.stdout)) as z:
        z.extractall(d)
    _LEGACY["dir"] = d
    import atexit
    atexit.register(shutil.rmtree, d, True)
    return d
