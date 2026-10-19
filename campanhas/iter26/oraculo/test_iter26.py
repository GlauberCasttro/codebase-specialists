"""ORÁCULO campanha-iter26 (0.14.0) — modelo de itens canônico, sem campos mortos, telemetria por tentativa.

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Tudo pelo caminho REAL: alvo da fixture do emit
(init + harness install + emit pela skill), estado em MODO ÁRVORE (`cs-state init`), comandos pelo `cs-state` do
próprio alvo (`.swarm/harness/state.py --root <alvo>`, o que `.swarm/bin/cs-state` chama), o `cs-mem` do alvo
(`.swarm/harness/mem.py --root <alvo>`, o que `.swarm/bin/cs-mem` chama) e o hook REAL
`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py subagent-stop`.

  CA-01  task nova (sprint, avulsa, de story — todas pelo `start` da árvore — e `add task --quick`) sem `dod`,
         `handoff`, `knowledge_context`, `briefing.context`, `briefing.scope.in`; o `add` não chama a busca do cs-mem;
         alvo 0.13.1 real com task antiga (campos mortos) continua despachando e validando.
  CA-02  `new epic`/`new epico` gravam `kind: "epic"`; arquivo antigo `kind: "epico"` lido (board/show/validate);
         demais campos do disco iguais aos da 0.13.1.
  CA-03  BUG da árvore com `--repro` (passos) e `--failing-test` ⇒ `repro_steps` e `failing_test` separados;
         BUG antigo (passos em `failing_test`) carrega sem perder o texto.
  CA-04  flags en (`--type/--as-a/--i-want/--so-that/--reason`, `new epic`) funcionam; pt funcionam igual com
         aviso de depreciação no stderr; help e textos emitidos sem as flags pt.
  CA-05  reject→retry→verify ×2 → accept ⇒ lista de rejeições e lista de gate por tentativa; o "último" igual.
  CA-06  subagent-stop com transcript sintético com `usage` ⇒ tokens junto do modelo medido; sem transcript NOT_RUN
         com motivo (nunca 0); transcript corrompido ⇒ falha registrada.
  CA-07  alvo 0.13.1 real (`git archive bac0e0f`): upgrade lista 0.14.0; apply reemite textos en; validate ok.
  CA-08  (B-49) caderno regravado pelo cs-mem entre dispatch e verify não é culpa da task; adulterado/outro arquivo
         em `.claude/` continua acusado.
  CA-09  (B-67) orquestrador emitido e saída do `close` (task/story/sprint) orientam `git add .swarm`.

Versão sempre RELATIVA (≥). Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill antiga: $CS_OLD_SKILL_DIR
ou `git archive bac0e0f`. Temporários: $CS_ORACLE_TMP, senão o TMPDIR do sistema. Python 3.9+, unittest, só stdlib.
Rodar (desta pasta): python3 -m unittest -v test_iter26
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
SKILL = os.path.realpath(os.environ.get("CS_SKILL_DIR") or PROJECT)
OLD_COMMIT = "bac0e0f"          # estado com a skill 0.13.1 (iter25 entregue + mudança oficial 02)
OLD_VERSION = (0, 13, 1)
NEW_VERSION = (0, 14, 0)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
OTHER = "dev-web"
VERIFY = "python3 -m unittest tests.test_ok"
ACEITE = "python3 -m unittest tests.test_red"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
STEPS = "1. Ana abre o carrinho 2. aplica o cupom ANA10 3. o total fica negativo"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
PT_FLAGS = re.compile(r"--(tipo|como|quero|para|motivo)\b")
PT_EPIC = re.compile(r"\bnew epico\b")
DEPREC = re.compile(r"deprec|obsolet|descontinuad", re.I)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEAD = ("dod", "handoff", "knowledge_context")
_TMP = {}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update({"GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0",
              "GIT_CONFIG_KEY_1": "maintenance.auto", "GIT_CONFIG_VALUE_1": "false",
              "GIT_CONFIG_KEY_2": "gc.autoDetach", "GIT_CONFIG_VALUE_2": "false"})
    e.update(extra or {})
    return e


def _run(argv, cwd, timeout=900, extra=None, stdin=None):
    p = subprocess.run(argv, cwd=cwd, env=_env(extra), input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(root, *args):
    code, out, err = _run(["git", "-C", root] + list(args), root)
    if code != 0:
        raise AssertionError("git %s: %s%s" % (" ".join(args), out, err))
    return out


def cs(skill, target, *args):
    return _run([sys.executable, os.path.join(skill, "scripts", "cs.py"), "--target", target] + list(args), target)


def cs_ok(skill, target, *args):
    code, out, err = cs(skill, target, *args)
    if code != 0:
        raise AssertionError("cs.py %s → %d\n%s\n%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def st(root, *args, actor=None):
    argv = [sys.executable, os.path.join(root, SD, "harness", "state.py"), "--root", root]
    if actor:
        argv += ["--actor", actor]
    return _run(argv + list(args), root)


def st_ok(root, *args, actor=None):
    code, out, err = st(root, *args, actor=actor)
    if code != 0:
        raise AssertionError("cs-state %s → %d\n%s%s" % (" ".join(args), code, out[-3000:], err[-3000:]))
    return out


def mem_ok(root, *args):
    code, out, err = _run([sys.executable, os.path.join(root, SD, "harness", "mem.py"), "--root", root] + list(args),
                          root)
    if code != 0:
        raise AssertionError("cs-mem %s → %d\n%s%s" % (" ".join(args), code, out[-2000:], err[-2000:]))
    return out


def new_id(root, *args):
    out = st_ok(root, "new", *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


def hook(root, mode, payload):
    p = dict(payload)
    p.setdefault("cwd", root)
    p.setdefault("session_id", "s-iter26")
    return _run([sys.executable, os.path.join(root, SD, "harness", "guard.py"), mode], root, timeout=120,
                extra={"CLAUDE_PROJECT_DIR": root}, stdin=json.dumps(p).encode())


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(root, rel, txt):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def vtuple(v):
    return tuple(int(x) for x in str(v).strip().split("."))


def _strip_json5(txt):
    out, i, n, s = [], 0, len(txt), None
    while i < n:
        c = txt[i]
        if s:
            out.append(c)
            if c == "\\":
                out.append(txt[i + 1])
                i += 2
                continue
            if c == s:
                s = None
        elif c in "\"'":
            s = c
            out.append(c)
        elif txt.startswith("//", i):
            while i < n and txt[i] != "\n":
                i += 1
            continue
        elif txt.startswith("/*", i):
            i = txt.index("*/", i) + 2
            continue
        else:
            out.append(c)
        i += 1
    t = "".join(out)
    t = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return json.loads(t)


def all_items(root):
    """{id: (zona, path, dict)} de todos os arquivos de item da árvore (backlog/state/archive)."""
    got = {}
    for zone in ("backlog", "state", "archive"):
        for dp, _, fns in os.walk(os.path.join(root, SD, zone)):
            for fn in fns:
                if not fn.endswith((".json", ".json5")):
                    continue
                p = os.path.join(dp, fn)
                try:
                    d = _strip_json5(read_text(p))
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("id") and d.get("kind"):
                    got[d["id"]] = (zone, p, d)
    return got


def item(root, iid):
    got = all_items(root)
    if iid not in got:
        raise AssertionError("item %s sem arquivo na árvore" % iid)
    return got[iid]


def projection(root):
    return json.loads(read_text(os.path.join(root, SD, ".engine", "projection.json")))


def m2_task(root, tid):
    for t in projection(root).get("tasks") or []:
        if t.get("id") == tid or t.get("tree_id") == tid:
            return t
    raise AssertionError("task M2 %s ausente da projeção" % tid)


def deleg(root, tid):
    ds = m2_task(root, tid).get("delegations") or []
    if not ds:
        raise AssertionError("task %s sem delegação" % tid)
    return ds[-1]


def walk_dicts(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            for y in walk_dicts(v):
                yield y
    elif isinstance(x, list):
        for v in x:
            for y in walk_dicts(v):
                yield y


def walk_lists(x):
    if isinstance(x, list):
        yield x
        for v in x:
            for y in walk_lists(v):
                yield y
    elif isinstance(x, dict):
        for v in x.values():
            for y in walk_lists(v):
                yield y


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            for y in strings(v):
                yield y
    elif isinstance(x, list):
        for v in x:
            for y in strings(v):
                yield y


def strip_volatile(x):
    """tira timestamps (chave `at` ou `*_at`) — o resto do item tem de ser igual entre versões."""
    if isinstance(x, dict):
        return {k: strip_volatile(v) for k, v in x.items() if k != "at" and not k.endswith("_at")}
    if isinstance(x, list):
        return [strip_volatile(v) for v in x]
    return x


# ================================================================================================ fixtures
def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter26-",
                                                         dir=os.environ.get("CS_ORACLE_TMP") or None))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP and not os.environ.get("CS_ORACLE_KEEP"):
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.13.1 real: $CS_OLD_SKILL_DIR ou `git archive` do commit (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-antiga")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.13.1 (git archive %s): %s — defina $CS_OLD_SKILL_DIR"
                                 % (OLD_COMMIT, p.stderr.decode()))
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(d, filter="data")
            else:
                tf.extractall(d)
    d = os.path.realpath(d)
    v = read_text(os.path.join(d, "VERSION")).strip()
    if vtuple(v) != OLD_VERSION:
        raise AssertionError("skill antiga em %s tem VERSION %s (esperado 0.13.1)" % (d, v))
    _TMP["old"] = d
    return d


def make_target(skill, name):
    dest = os.path.join(_base_tmp(), name)
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r);"
            "import fixture; print(fixture.make_repo())"
            % (os.path.join(skill, "scripts"), os.path.join(skill, "scripts", "emit", "tests")))
    rc, out, err = _run([sys.executable, "-c", code], _base_tmp())
    if rc != 0:
        raise AssertionError("fixture do emit: %s%s" % (out, err))
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(out.strip().splitlines()[-1], dest)
    write(dest, "tests/__init__.py", "")
    write(dest, "tests/test_ok.py", "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                                    "        self.assertTrue(True)\n")
    write(dest, "tests/test_red.py", "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_red(self):\n"
                                     "        self.assertTrue(False, 'bug da Ana')\n")
    for f in ("coupons.py", "pix.py", "frete.py", "taxa.py", "nota.py", "q.py", "bug.py", "flat.py", "solta.py"):
        write(dest, "src/billing/" + f, "X = 1\n")
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    st_ok(dest, "init")
    if not os.path.isfile(os.path.join(dest, SD, "events.jsonl")):
        raise AssertionError("fixture: o alvo não ficou em modo árvore (.swarm/events.jsonl ausente)")
    return dest


def clone(src, name):
    dst = os.path.join(_base_tmp(), name)
    for attempt in range(3):
        shutil.rmtree(dst, ignore_errors=True)
        try:
            shutil.copytree(src, dst, symlinks=True)
            return dst
        except shutil.Error:
            if attempt == 2:
                raise
    return dst


def _us(title, path, *extra):
    """flags pt: valem na 0.13.1 e (como alias depreciado) na 0.14.0 — a fixture roda nas duas."""
    return ["--tipo", "US", "--agent", AGENT, "--title", title, "--allowed-path", path, "--verify-cmd", VERIFY,
            "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", C1] + list(extra)


def populate(root):
    """Árvore da Ana: EPC › SPR › FEA › story (2 tasks); 2 tasks na sprint; 1 avulsa; 1 no backlog."""
    ids = {}
    ids["epc"] = new_id(root, "epico", "--title", "Pagamentos da Ana", "--objetivo", "pix")
    ids["spr"] = new_id(root, "sprint", "--meta", "pix da Ana", "--epico", ids["epc"])
    st_ok(root, "start", ids["epc"])
    st_ok(root, "start", ids["spr"])
    ids["fea"] = new_id(root, "feature", "--title", "Pix da Ana", "--sprint", ids["spr"], "--aceite", ACEITE)
    st_ok(root, "start", ids["fea"])
    ids["story"] = new_id(root, "story", "--tipo", "US", "--title", "Story da Ana", "--feature", ids["fea"],
                          "--agents", AGENT, "--agents", OTHER, "--allowed-path", "src/billing/q.py",
                          "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "x", "--para", "y", "--criterio", C1)
    ids["st1"], ids["st2"] = ids["story"] + "/01", ids["story"] + "/02"
    st_ok(root, "amend", ids["st1"], "--field", "allowed_paths", "--after", '["src/billing/q.py"]', "--reason",
          "estreitar o territorio da Ana")
    ids["task"] = new_id(root, "task", *_us("Cupom da Ana", "src/billing/coupons.py", "--sprint", ids["spr"]))
    ids["task2"] = new_id(root, "task", *_us("Taxa da Ana", "src/billing/taxa.py", "--sprint", ids["spr"]))
    ids["avulsa"] = new_id(root, "task", *_us("Solta da Ana", "src/billing/solta.py", "--avulsa"))
    ids["bkl"] = new_id(root, "task", *_us("Nota da Ana", "src/billing/nota.py", "--backlog"))
    return ids


def fresh_base():
    if "fresh" not in _TMP:
        root = make_target(SKILL, "base-nova")
        _TMP["fresh"] = (root, populate(root))
    return _TMP["fresh"]


_N = [0]


def fresh(tag):
    _N[0] += 1
    src, ids = fresh_base()
    return clone(src, "nova-%s-%d" % (tag, _N[0])), dict(ids)


def recommended(out):
    m = re.findall(r"model='([a-z]+)'", out)
    return m[-1] if m else "sonnet"


def dispatch(root, tid, model=None):
    code, out, err = st(root, "dispatch", tid, "--manual", "--model", model or "sonnet")
    if code != 0 and "recomenda" in (out + err):
        code, out, err = st(root, "dispatch", tid, "--manual", "--model", recommended(out + err))
    if code != 0:
        raise AssertionError("dispatch %s → %d\n%s%s" % (tid, code, out, err))
    return out


def submit(root, tid, path, content):
    write(root, path, content)
    return st_ok(root, "submit", tid, "--files-changed", path, "--check", "unittest: OK", "--risk", "nenhum",
                 "--handoff-notes", "consultei: nada — oráculo", actor=AGENT)


def start_and_dispatch(root, tid):
    out = st_ok(root, "start", tid)
    dispatch(root, tid, recommended(out))


# ================================================================================================ fixture legada
def legacy_base():
    """Alvo instalado pela skill 0.13.1 REAL com task antiga iniciada (M2 com campos mortos) e BUG antigo."""
    if "legacy" in _TMP:
        return _TMP["legacy"]
    root = make_target(old_skill(), "base-legado")
    ids = populate(root)
    st_ok(root, "start", ids["task"])                       # M2 antigo: dod/handoff/knowledge_context/briefing
    ids["bug"] = new_id(root, "task", "--tipo", "BUG", "--agent", AGENT, "--title", "Bug antigo da Ana",
                        "--allowed-path", "src/billing/bug.py", "--verify-cmd", VERIFY, "--reproducao", STEPS,
                        "--sprint", ids["spr"])
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "itens da Ana")
    t = m2_task(root, ids["task"])
    if not all(k in t for k in DEAD):
        raise AssertionError("fixture: a task antiga deveria ter os campos mortos %s: %s" % (DEAD, sorted(t)))
    _TMP["legacy"] = (root, ids)
    return _TMP["legacy"]


def upgraded():
    if "up" not in _TMP:
        src, ids = legacy_base()
        root = clone(src, "base-legado-atualizado")
        r = {"root": root, "ids": ids, "items0": all_items(root)}
        r["board0"] = st(root, "board")
        r["show0"] = {k: st(root, "show", ids[k]) for k in ("epc", "bug", "task")}
        r["plan"] = cs(SKILL, root, "upgrade")
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        r["items1"] = all_items(root)
        _TMP["up"] = r
    return _TMP["up"]


def up_clone(tag):
    r = upgraded()
    _N[0] += 1
    return clone(r["root"], "legado-%s-%d" % (tag, _N[0])), dict(r["ids"])


def emitted_text_lines(root):
    """[(rel, nº, linha)] dos textos emitidos (CLAUDE.md, .claude/**, Makefile/*.mk, AGENTS.md, .cursor, .github),
    fora de código do motor (.swarm/harness) e de dados (.swarm/state|backlog|archive)."""
    got = []
    cands = []
    for rel in ("CLAUDE.md", "AGENTS.md", "Makefile", "specialists.mk"):
        if os.path.isfile(os.path.join(root, rel)):
            cands.append(rel)
    for d in (".claude", ".cursor", ".github", os.path.join(SD, "emit")):
        for dp, _, fns in os.walk(os.path.join(root, d)):
            if "agent-memory" in dp:
                continue
            for fn in fns:
                if fn.endswith((".md", ".mdc", ".mk", ".txt", ".json", ".json5", ".sh")):
                    cands.append(os.path.relpath(os.path.join(dp, fn), root))
    for rel in cands:
        try:
            txt = read_text(os.path.join(root, rel))
        except (UnicodeDecodeError, OSError):
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            got.append((rel, i, ln))
    return got


def pt_hits(root):
    """linhas de texto emitido que citam flag/subcomando pt de cs-state (o cs-auto/M5 está fora do escopo)."""
    return ["%s:%d: %s" % (r, i, ln.strip()[:140]) for r, i, ln in emitted_text_lines(root)
            if "cs-auto" not in ln and (PT_FLAGS.search(ln) or PT_EPIC.search(ln))]


# ================================================================================================ CA-01
SPY = r"""
import os, sys
sys.dont_write_bytecode = True
root, log = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, ".swarm", "harness"))
import mem
def spy(name, fn):
    def w(*a, **k):
        with open(log, "a") as f:
            f.write(name + "\n")
        return fn(*a, **k)
    return w
mem.search = spy("mem.search", mem.search)
for _n in dir(mem):
    _c = getattr(mem, _n)
    if isinstance(_c, type) and callable(getattr(_c, "search", None)):
        setattr(_c, "search", spy(_n + ".search", _c.search))
"""
SPY_STATE = SPY + 'import state\nsys.exit(state.main(["--root", root] + sys.argv[3:]))\n'
SPY_SELF = SPY + 'mem.search(root, "cupom", k=1)\n'


def spied(root, *args):
    """roda o `cs-state` do alvo com a busca do cs-mem (mem.search e <Classe>.search) instrumentada."""
    log = os.path.join(_base_tmp(), "spy-%d.log" % len(os.listdir(_base_tmp())))
    code, out, err = _run([sys.executable, "-c", SPY_STATE, root, log] + list(args), root)
    calls = read_text(log).split() if os.path.isfile(log) else []
    return code, out, err, calls


def _dead(t):
    bad = [k for k in DEAD if k in t]
    br = t.get("briefing") or {}
    if "context" in br:
        bad.append("briefing.context")
    if "in" in (br.get("scope") or {}):
        bad.append("briefing.scope.in")
    return bad


class TestCA01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.ids = fresh("ca01")
        for k in ("task", "avulsa", "st1"):
            st_ok(cls.root, "start", cls.ids[k])
        st_ok(cls.root, "session", "start", "--request", "ajuste pequeno da Ana")
        st_ok(cls.root, "session", "triage", "--class", "pequena", "--why", "um arquivo")
        cls.add = spied(cls.root, "add", "task", "--quick", "--agent", AGENT, "--title", "Flat da Ana",
                        "--allowed-path", "src/billing/flat.py", "--verify-cmd", VERIFY)

    def _check(self, key):
        bad = _dead(m2_task(self.root, self.ids[key]))
        self.assertEqual(bad, [], "task %s (%s) não deveria gravar campos mortos: %s" % (self.ids[key], key, bad))

    def test_ca01_task_da_sprint_sem_campos_mortos(self):
        self._check("task")

    def test_ca01_task_avulsa_sem_campos_mortos(self):
        self._check("avulsa")

    def test_ca01_task_de_story_sem_campos_mortos(self):
        self._check("st1")

    def test_ca01_add_task_sem_campos_mortos(self):
        code, out, err, _ = self.add
        self.assertEqual(code, 0, out + err)
        ts = [t for t in projection(self.root)["tasks"] if t.get("title") == "Flat da Ana"]
        self.assertEqual(len(ts), 1)
        self.assertEqual(_dead(ts[0]), [], "add task não deveria gravar campos mortos")

    def test_ca01_add_task_nao_busca_na_memoria(self):
        code, out, err, calls = self.add
        self.assertEqual(code, 0, out + err)
        self.assertEqual(calls, [], "o `add task` não deveria chamar a busca do cs-mem (knowledge_context morto)")

    def test_ca01_controle_espiao_ve_a_busca(self):
        """controle: o espião registra a busca quando ela acontece (o teste acima não é vácuo)."""
        log = os.path.join(_base_tmp(), "spy-controle.log")
        code, out, err = _run([sys.executable, "-c", SPY_SELF, self.root, log], self.root)
        self.assertEqual(code, 0, out + err)
        self.assertIn("mem.search", read_text(log))

    def test_ca01_controle_task_antiga_continua_despachando_e_validando(self):
        """alvo 0.13.1 real: task iniciada com dod/handoff/knowledge_context/briefing; depois do upgrade carrega,
        despacha, submete, verifica e `validate --strict` sai 0."""
        root, ids = up_clone("ca01")
        tid = ids["task"]
        t = m2_task(root, tid)
        self.assertTrue(all(k in t for k in DEAD), "pré-condição: task antiga com campos mortos")
        st_ok(root, "show", tid)
        dispatch(root, tid)
        submit(root, tid, "src/billing/coupons.py", "X = 2\n")
        out = st_ok(root, "verify", tid)
        self.assertIn("PASS", out, out)
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, "validate --strict com task antiga: %s%s" % (out[-2000:], err[-2000:]))


# ================================================================================================ CA-02
def _shown(r):
    code, out, err = r
    return code, out


class TestCA02(unittest.TestCase):
    def test_ca02_new_epic_grava_kind_epic(self):
        root, _ = fresh("ca02a")
        eid = new_id(root, "epic", "--title", "Fiscal da Ana", "--objetivo", "nota")
        self.assertEqual(item(root, eid)[2].get("kind"), "epic")

    def test_ca02_alias_new_epico_grava_kind_epic(self):
        root, _ = fresh("ca02b")
        eid = new_id(root, "epico", "--title", "Fiscal da Ana", "--objetivo", "nota")
        self.assertEqual(item(root, eid)[2].get("kind"), "epic")

    def test_ca02_populate_grava_epic(self):
        root, ids = fresh("ca02c")
        self.assertEqual(item(root, ids["epc"])[2].get("kind"), "epic")

    def test_ca02_controle_arquivo_antigo_epico_continua_lido(self):
        """alvo 0.13.1 (kind "epico" no disco) depois do upgrade: board/show iguais, validate ok, épico listado."""
        r = upgraded()
        root, ids = r["root"], r["ids"]
        self.assertEqual(r["items0"][ids["epc"]][2].get("kind"), "epico", "pré-condição: arquivo antigo")
        self.assertIn(item(root, ids["epc"])[2].get("kind"), ("epico", "epic"))
        self.assertEqual(_shown(st(root, "board")), _shown(r["board0"]), "board mudou depois do upgrade")
        self.assertEqual(_shown(st(root, "show", ids["epc"])), _shown(r["show0"]["epc"]), "show do épico mudou")
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, out + err)

    def test_ca02_controle_demais_campos_iguais_a_0131(self):
        """mesmos comandos na 0.13.1 real e na skill sob teste: todo item igual (sem timestamps), exceto `kind` do
        épico (epico → epic)."""
        src, ids_old = legacy_base()
        old = all_items(src)
        root, ids = fresh("ca02d")
        new = all_items(root)
        bad = []
        for k in ("epc", "spr", "fea", "story", "st1", "st2", "task", "task2", "avulsa", "bkl"):
            a, b = strip_volatile(old[ids_old[k]][2]), strip_volatile(new[ids[k]][2])
            if k == "task":
                continue  # na legada a task foi iniciada (history diferente)
            for d in (a, b):
                if d.get("kind") in ("epico", "epic"):
                    d["kind"] = "epic"
            if a != b:
                ks = sorted(x for x in set(a) | set(b) if a.get(x) != b.get(x))
                bad.append("%s (%s): %s" % (ids[k], k, ks))
        self.assertEqual(bad, [], "campos do disco diferentes da 0.13.1:\n  " + "\n  ".join(bad))


# ================================================================================================ CA-03
def _bug_args(*extra):
    return ["--type", "BUG", "--agent", AGENT, "--title", "Bug do cupom da Ana", "--allowed-path",
            "src/billing/bug.py", "--verify-cmd", VERIFY] + list(extra)


def _txt(v):
    return "\n".join(v) if isinstance(v, list) else (v or "")


class TestCA03(unittest.TestCase):
    def test_ca03_bug_grava_repro_steps_e_failing_test(self):
        root, ids = fresh("ca03a")
        bid = new_id(root, "task", *_bug_args("--repro", STEPS, "--failing-test", "tests.test_red",
                                              "--sprint", ids["spr"]))
        d = item(root, bid)[2]
        self.assertIn(STEPS, _txt(d.get("repro_steps")), "passos em repro_steps: %s" % d)
        self.assertEqual(d.get("failing_test"), "tests.test_red", "teste que falha em failing_test: %s" % d)
        self.assertNotIn(STEPS, _txt(d.get("failing_test")))

    def test_ca03_bug_inicia_com_teste_vermelho(self):
        """o DoR do BUG roda o failing_test (vermelho) — os passos não são executados como teste."""
        root, ids = fresh("ca03b")
        bid = new_id(root, "task", *_bug_args("--repro", STEPS, "--failing-test", "tests.test_red",
                                              "--sprint", ids["spr"]))
        st_ok(root, "start", bid)
        self.assertEqual(m2_task(root, bid).get("tree_id"), bid)

    def test_ca03_controle_bug_antigo_continua_com_o_texto(self):
        """BUG da 0.13.1 (passos em `failing_test`): depois do upgrade o texto continua no arquivo e no show."""
        r = upgraded()
        root, bid = r["root"], r["ids"]["bug"]
        self.assertIn(STEPS, json.dumps(r["items0"][bid][2], ensure_ascii=False), "pré-condição")
        self.assertIn(STEPS, json.dumps(item(root, bid)[2], ensure_ascii=False), "o texto sumiu do arquivo")
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, out + err)

    def test_ca03_bug_antigo_show_traz_os_passos(self):
        """BUG da 0.13.1 lido pela skill sob teste: o `show` traz os passos (lidos como passos, sem perder o texto)."""
        r = upgraded()
        code, out, err = st(r["root"], "show", r["ids"]["bug"])
        self.assertEqual(code, 0, out + err)
        self.assertIn(STEPS, out, "show do BUG antigo deveria trazer os passos de reprodução")

    def test_ca03_bug_novo_show_traz_passos_e_teste(self):
        root, ids = fresh("ca03c")
        bid = new_id(root, "task", *_bug_args("--repro", STEPS, "--failing-test", "tests.test_red",
                                              "--sprint", ids["spr"]))
        out = st_ok(root, "show", bid)
        self.assertIn(STEPS, out)
        self.assertIn("tests.test_red", out)


# ================================================================================================ CA-04
EN_TASK = ["--type", "US", "--agent", AGENT, "--title", "Cupom en da Ana", "--allowed-path", "src/billing/pix.py",
           "--verify-cmd", VERIFY, "--as-a", "cliente", "--i-want", "cupom", "--so-that", "pagar menos",
           "--criterio", C1]
PT_TASK = ["--tipo", "US", "--agent", AGENT, "--title", "Cupom pt da Ana", "--allowed-path", "src/billing/frete.py",
           "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", C1]


def _core(d):
    d = strip_volatile(d)
    for k in ("id", "title", "path", "allowed_paths", "aliases", "history"):
        d.pop(k, None)
    return d


class TestCA04(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.ids = fresh("ca04")

    def test_ca04_flags_en_criam_task_us(self):
        tid = new_id(self.root, "task", *(EN_TASK + ["--sprint", self.ids["spr"]]))
        d = item(self.root, tid)[2]
        self.assertEqual((d.get("type"), d.get("as_a"), d.get("i_want"), d.get("so_that")),
                         ("US", "cliente", "cupom", "pagar menos"))

    def test_ca04_flag_en_reason_cria_chore(self):
        tid = new_id(self.root, "task", "--type", "CHORE", "--agent", AGENT, "--title", "Limpeza da Ana",
                     "--allowed-path", "src/billing/q.py", "--verify-cmd", VERIFY, "--reason", "divida tecnica",
                     "--sprint", self.ids["spr"])
        self.assertEqual(item(self.root, tid)[2].get("reason"), "divida tecnica")

    def test_ca04_flags_pt_avisam_depreciacao(self):
        code, out, err = st(self.root, "new", "task", *(PT_TASK + ["--backlog"]))
        self.assertEqual(code, 0, out + err)
        self.assertRegex(err, DEPREC, "flag pt deveria imprimir aviso de depreciação no stderr")

    def test_ca04_new_epico_avisa_depreciacao(self):
        code, out, err = st(self.root, "new", "epico", "--title", "Outro da Ana", "--objetivo", "x")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(err, DEPREC, "`new epico` deveria imprimir aviso de depreciação no stderr")

    def test_ca04_pt_e_en_gravam_igual(self):
        root, ids = fresh("ca04b")
        a = new_id(root, "task", *(EN_TASK + ["--backlog"]))
        b = new_id(root, "task", *(PT_TASK + ["--backlog"]))
        self.assertEqual(_core(item(root, a)[2]), _core(item(root, b)[2]))

    def test_ca04_help_sem_flags_pt(self):
        bad = []
        for args in (["new", "task", "--help"], ["new", "story", "--help"], ["new", "--help"]):
            code, out, err = st(self.root, *args)
            if code != 0 or PT_FLAGS.search(out) or re.search(r"\bepico\b", out):
                bad.append("%s → %d: %s" % (" ".join(args), code,
                                            sorted(set(PT_FLAGS.findall(out)) | set(re.findall(r"\bepico\b", out)))))
        self.assertEqual(bad, [], "help deveria citar só o inglês:\n  " + "\n  ".join(bad))

    def test_ca04_textos_emitidos_sem_flags_pt(self):
        hits = pt_hits(self.root)
        self.assertEqual(hits, [], "textos emitidos com flag pt (%d):\n  %s" % (len(hits), "\n  ".join(hits[:30])))

    def test_ca04_controle_flags_pt_continuam_criando(self):
        tid = new_id(self.root, "task", *(PT_TASK + ["--sprint", self.ids["spr"]]))
        d = item(self.root, tid)[2]
        self.assertEqual((d.get("type"), d.get("as_a")), ("US", "cliente"))


# ================================================================================================ CA-05
R1, R2 = "faltou o caso do cupom vencido da Ana", "faltou o arredondamento da Ana"


def _int_vals(d, rx):
    return [v for k, v in d.items() if re.search(rx, k, re.I) and isinstance(v, int) and not isinstance(v, bool)]


def _has_iso(d):
    return any(isinstance(v, str) and ISO.match(v) for v in d.values())


def rejection_list(t):
    """lista (em qualquer lugar da task) cujos elementos trazem motivo, tentativa, quem e quando."""
    for L in walk_lists(t):
        ds = [x for x in L if isinstance(x, dict)]
        if len(ds) < 2:
            continue
        txt = [" ".join(strings(x)) for x in ds]
        if not (any(R1 in s for s in txt) and any(R2 in s for s in txt)):
            continue
        att = [(_int_vals(x, r"attempt|tentativa") or [None])[0] for x in ds]
        who = all(any(isinstance(v, str) and v == "lead" for v in x.values()) for x in ds)
        if None not in att and len(set(att)) == len(att) and who and all(_has_iso(x) for x in ds):
            return ds
    return None


def gate_list(t):
    """lista cujos elementos trazem tentativa, exit, sha(s) e quando — uma por verify."""
    for L in walk_lists(t):
        ds = [x for x in L if isinstance(x, dict)]
        if len(ds) < 3:
            continue
        ok = True
        for x in ds:
            flat = {}
            for y in walk_dicts(x):
                flat.update(y)
            if not (_int_vals(flat, r"attempt|tentativa") and _int_vals(flat, r"exit")
                    and any(isinstance(v, str) and HEX64.match(v) for v in strings(x)) and _has_iso(flat)):
                ok = False
                break
        if ok:
            atts = []
            for x in ds:
                flat = {}
                for y in walk_dicts(x):
                    flat.update(y)
                atts.append(_int_vals(flat, r"attempt|tentativa")[0])
            if len(set(atts)) == len(atts) == 3:
                return ds
    return None


def _ca05_flow():
    if "ca05" in _TMP:
        return _TMP["ca05"]
    root, ids = fresh("ca05")
    tid = ids["task"]
    snaps = {}
    start_and_dispatch(root, tid)
    submit(root, tid, "src/billing/coupons.py", "X = 2\n")
    st_ok(root, "verify", tid)
    st_ok(root, "reject", tid, "--reason", R1)
    snaps["rej1"] = m2_task(root, tid)
    out = st_ok(root, "retry", tid, "--findings", "refazer 1")
    dispatch(root, tid, recommended(out))
    submit(root, tid, "src/billing/coupons.py", "X = 3\n")
    st_ok(root, "verify", tid)
    st_ok(root, "reject", tid, "--reason", R2)
    snaps["rej2"] = m2_task(root, tid)
    out = st_ok(root, "retry", tid, "--findings", "refazer 2")
    dispatch(root, tid, recommended(out))
    submit(root, tid, "src/billing/coupons.py", "X = 4\n")
    st_ok(root, "verify", tid)
    snaps["ver3"] = m2_task(root, tid)
    st_ok(root, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido")
    st_ok(root, "accept", tid)
    snaps["acc"] = m2_task(root, tid)
    _TMP["ca05"] = (root, tid, snaps)
    return _TMP["ca05"]


class TestCA05(unittest.TestCase):
    def test_ca05_lista_de_rejeicoes(self):
        root, tid, s = _ca05_flow()
        self.assertIsNotNone(rejection_list(s["acc"]),
                             "a task aceita deveria guardar as 2 rejeições (tentativa, motivo, quem, quando)")

    def test_ca05_lista_de_gate_por_tentativa(self):
        root, tid, s = _ca05_flow()
        self.assertIsNotNone(gate_list(s["acc"]),
                             "a task aceita deveria guardar o gate de cada uma das 3 tentativas (exit, shas, quando)")

    def test_ca05_ultimo_reject_reason_igual_ao_ultimo_elemento(self):
        root, tid, s = _ca05_flow()
        L = rejection_list(s["rej2"])
        self.assertIsNotNone(L, "depois da 2ª rejeição a lista deveria ter as 2")
        self.assertEqual(s["rej2"].get("reject_reason"), R2)
        self.assertIn(R2, " ".join(strings(L[-1])))

    def test_ca05_ultimo_gate_report_igual_ao_ultimo_elemento(self):
        root, tid, s = _ca05_flow()
        L = gate_list(s["acc"])
        self.assertIsNotNone(L, "lista de gate ausente")
        b = (s["acc"].get("gate_report") or {}).get("build") or {}
        self.assertIn(b.get("output_sha256"), list(strings(L[-1])), "último gate ≠ gate_report.build")

    def test_ca05_controle_reject_reason_continua(self):
        root, tid, s = _ca05_flow()
        self.assertEqual(s["rej1"].get("reject_reason"), R1)
        self.assertEqual(s["rej2"].get("reject_reason"), R2)
        self.assertEqual(((s["acc"].get("gate_report") or {}).get("build") or {}).get("exit_code"), 0)
        self.assertEqual(s["acc"].get("status"), "ACCEPTED")


# ================================================================================================ CA-06
USAGE = [{"input_tokens": 1000, "output_tokens": 200, "cache_creation_input_tokens": 30,
          "cache_read_input_tokens": 250},
         {"input_tokens": 100, "output_tokens": 50, "cache_creation_input_tokens": 10,
          "cache_read_input_tokens": 50}]


def transcript(path, kind):
    lines = [json.dumps({"type": "user", "message": {"role": "user", "content": "task da Ana"}})]
    if kind == "ok":
        for i, u in enumerate(USAGE, 1):
            lines.append(json.dumps({"type": "assistant", "message": {
                "id": "msg_ana_%d" % i, "role": "assistant", "model": "claude-sonnet-4-5", "usage": u,
                "content": [{"type": "text", "text": "ok"}]}}))
    else:
        lines.append('{"type": "assistant", "message": {"id": "msg_ana_1", "model": "claude-sonnet-4-5", '
                     '"usage": {"input_tokens": "mil", "output_tokens": ')
        lines.append('{"type": "assistant", "message": {"model": "claude-sonnet-4-5", "usage": [[[')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _stop(tag, kind):
    root, ids = fresh("ca06" + tag)
    tid = ids["task"]
    start_and_dispatch(root, tid)
    led0 = _ledger(root)
    payload = {"hook_event_name": "SubagentStop", "agent_type": AGENT, "agent_id": "ag-ana",
               "stop_hook_active": False}
    if kind != "none":
        payload["agent_transcript_path"] = transcript(os.path.join(root, "..", "tr-%s-%s.jsonl" % (tag, kind)), kind)
    code, out, err = hook(root, "subagent-stop", payload)
    return root, tid, (code, out, err), _ledger(root)[len(led0):]


def _ledger(root):
    p = os.path.join(root, SD, "state", "ledger.jsonl")
    return read_text(p).splitlines() if os.path.isfile(p) else []


def _tok_dicts(d):
    return [x for x in walk_dicts(d) if any(re.search(r"input", k, re.I) for k in x)
            and any(re.search(r"output", k, re.I) for k in x)]


class TestCA06(unittest.TestCase):
    def test_ca06_tokens_junto_do_modelo_medido(self):
        root, tid, r, _ = _stop("a", "ok")
        d = deleg(root, tid)
        self.assertEqual((d.get("model") or {}).get("procedencia"), "medida", d.get("model"))
        hit = [x for x in _tok_dicts(d) if 1100 in _int_vals(x, r"input") and 250 in _int_vals(x, r"output")
               and set(_int_vals(x, r"cache")) & {300, 40, 340}]
        self.assertTrue(hit, "delegação deveria ter tokens (input 1100, output 250, cache 300/40) do transcript: %s"
                        % json.dumps({k: v for k, v in d.items() if k not in ("baseline", "route")})[:1500])

    def test_ca06_sem_transcript_not_run_com_motivo(self):
        root, tid, r, _ = _stop("b", "none")
        d = deleg(root, tid)
        s = list(strings(d))
        self.assertIn("NOT_RUN", s, "sem transcript a delegação deveria gravar NOT_RUN")
        zeros = [x for x in _tok_dicts(d) if 0 in _int_vals(x, r"input|output|cache|token")]
        self.assertEqual(zeros, [], "sem transcript nunca grava 0 tokens")
        nr = [x for x in walk_dicts(d) if "NOT_RUN" in x.values()]
        self.assertTrue(nr and any(len(v) > 8 for v in strings(nr[0]) if v != "NOT_RUN"),
                        "NOT_RUN deveria vir com o motivo: %s" % nr)

    def test_ca06_transcript_corrompido_registra_falha(self):
        root, tid, r, led = _stop("c", "bad")
        d = deleg(root, tid)
        tok = [x for x in walk_dicts(d) if any(re.search(r"token|usage", k, re.I) for k in x)
               or any(re.search(r"token|usage", k, re.I) for k in d)]
        marks = re.compile(r"ERROR|FAIL|falh|erro|corromp|invalid", re.I)
        in_deleg = any(marks.search(v) for x in walk_dicts(d) for k, v in x.items()
                       if isinstance(v, str) and re.search(r"token|usage|status|error|erro|reason|motivo", k, re.I))
        in_ledger = any(marks.search(ln) and ("usage" in ln or "token" in ln) for ln in led)
        self.assertTrue(in_deleg or in_ledger, "falha da medição de tokens deveria ficar registrada (delegação ou "
                        "ledger); delegação=%s ledger=%s" % (tok[:3], led[-3:]))
        self.assertEqual([x for x in _tok_dicts(d) if 0 in _int_vals(x, r"input|output")], [],
                         "falha não vira 0 tokens")

    def test_ca06_controle_modelo_medido_continua(self):
        root, tid, r, _ = _stop("d", "ok")
        m = deleg(root, tid).get("model") or {}
        self.assertEqual((m.get("name"), m.get("procedencia")), ("sonnet", "medida"))
        self.assertIn("block", r[1], "o hook continua pedindo o submit: %s" % (r,))


# ================================================================================================ CA-07
class TestCA07(unittest.TestCase):
    def test_ca07_version_e_catalogo_0140(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.14.0" % v)
        cat = _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.14.0"]
        self.assertEqual(len(ents), 1, "catálogo deveria ter exatamente uma entrada to: 0.14.0")
        kinds = {a.get("kind") for a in ents[0].get("actions") or []}
        self.assertTrue({"harness", "emit"} <= kinds, "a 0.14.0 reinstala harness e reemite: %s" % kinds)

    def test_ca07_plano_lista_0140(self):
        r = upgraded()
        code, out, err = r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertIn("0.14.0", out + err, "o plano deveria listar a 0.14.0")

    def test_ca07_apply_reemite_textos_em_ingles(self):
        r = upgraded()
        self.assertEqual(r["apply"][0], 0, r["apply"][1][-1500:] + r["apply"][2][-1500:])
        hits = pt_hits(r["root"])
        self.assertEqual(hits, [], "depois do upgrade os textos emitidos citam flag pt:\n  " + "\n  ".join(hits[:20]))

    def test_ca07_controle_fixture_legada_tem_texto_pt(self):
        """controle: o alvo 0.13.1 tem textos pt (o teste acima não é vácuo)."""
        src, _ = legacy_base()
        self.assertTrue(pt_hits(src))

    def test_ca07_controle_validate_strict_continua_depois_do_upgrade(self):
        r = upgraded()
        self.assertEqual(r["apply"][0], 0, r["apply"][1][-1500:] + r["apply"][2][-1500:])
        code, out, err = st(r["root"], "validate", "--strict")
        self.assertEqual(code, 0, "validate --strict depois do upgrade: %s%s" % (out[-2000:], err[-2000:]))

    def test_ca07_controle_itens_antigos_continuam_legiveis(self):
        r = upgraded()
        self.assertEqual(set(r["items1"]), set(r["items0"]), "o upgrade não cria nem remove item")
        bad = []
        for iid in sorted(r["items1"]):
            code, out, err = st(r["root"], "show", iid)
            if code != 0 or iid not in out:
                bad.append("%s → %d %s" % (iid, code, err[-200:]))
        self.assertEqual(bad, [], "\n  ".join(bad))


# ================================================================================================ CA-08
def _nb(agent):
    return ".claude/agent-memory/%s/MEMORY.md" % agent


def _ca08(tag, between):
    """start → dispatch → submit da task2 (dev-billing, src/billing/taxa.py); `between(root)`; verify."""
    root, ids = fresh("ca08" + tag)
    tid = ids["task2"]
    start_and_dispatch(root, tid)
    submit(root, tid, "src/billing/taxa.py", "X = 9\n")
    between(root)
    code, out, err = st(root, "verify", tid)
    return code, out + err


def _accused(txt, rel):
    return [ln for ln in txt.splitlines() if rel in ln and ln.lstrip().startswith("-")]


def _correct(agent):
    def f(root):
        mem_ok(root, "correct", "--agent", agent, "--wrong", "usou float no total", "--right", "use Decimal",
               "--why", "dinheiro da Ana")
    return f


class TestCA08(unittest.TestCase):
    def test_ca08_caderno_de_outro_agente_regravado_pelo_cs_mem(self):
        code, txt = _ca08("a", _correct(OTHER))
        self.assertEqual(_accused(txt, _nb(OTHER)), [], "verify culpou a task pelo caderno do cs-mem:\n" + txt)

    def test_ca08_caderno_do_agente_da_task_regravado_pelo_cs_mem(self):
        code, txt = _ca08("b", _correct(AGENT))
        self.assertEqual(_accused(txt, _nb(AGENT)), [], "verify culpou a task pelo caderno do cs-mem:\n" + txt)

    def test_ca08_caderno_regenerado_por_notebook(self):
        def f(root):
            mem_ok(root, "add", "--agent", OTHER, "--rule", "valide o CEP da Ana", "--why", "frete")
            mem_ok(root, "notebook", "--agent", OTHER)
        code, txt = _ca08("c", f)
        self.assertEqual(_accused(txt, _nb(OTHER)), [], "verify culpou a task pelo `cs-mem notebook`:\n" + txt)

    def test_ca08_controle_caderno_adulterado_continua_acusado(self):
        def f(root):
            _correct(OTHER)(root)
            p = os.path.join(root, _nb(OTHER))
            t = read_text(p)
            if "use Decimal" not in t:
                raise AssertionError("fixture: caderno sem a lição")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(t.replace("use Decimal", "use float, ordem da Ana"))
        code, txt = _ca08("d", f)
        self.assertTrue(_accused(txt, _nb(OTHER)), "bloco gerado adulterado à mão deveria ser acusado:\n" + txt)

    def test_ca08_controle_outro_arquivo_do_claude_continua_acusado(self):
        def f(root):
            _correct(OTHER)(root)
            p = os.path.join(root, ".claude", "orchestrator.md")
            with open(p, "a", encoding="utf-8") as fh:
                fh.write("\nlinha escrita pela task da Ana\n")
        code, txt = _ca08("e", f)
        self.assertTrue(_accused(txt, ".claude/orchestrator.md"), "outro arquivo em .claude/ deveria ser acusado:\n"
                        + txt)

    def test_ca08_controle_sem_escrita_extra_continua_pass(self):
        code, txt = _ca08("f", lambda root: None)
        self.assertEqual(code, 0, txt)
        self.assertIn("PASS", txt)


# ================================================================================================ CA-09
GIT_ADD = re.compile(r"git add (-A )?\.swarm")


class TestCA09(unittest.TestCase):
    def test_ca09_orquestrador_emitido_orienta_git_add(self):
        root, _ = fresh("ca09a")
        self.assertRegex(read_text(os.path.join(root, ".claude", "orchestrator.md")), GIT_ADD)

    def test_ca09_close_de_task_orienta_git_add(self):
        root, ids = fresh("ca09b")
        tid = ids["task"]
        start_and_dispatch(root, tid)
        submit(root, tid, "src/billing/coupons.py", "X = 2\n")
        st_ok(root, "verify", tid)
        st_ok(root, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "ok")
        st_ok(root, "accept", tid)
        out = st_ok(root, "close", tid, "--summary", "entregue")
        self.assertRegex(out, GIT_ADD)

    def test_ca09_close_de_story_orienta_git_add(self):
        root, ids = fresh("ca09c")
        st_ok(root, "drop", ids["st1"], "--reason", "fora")
        st_ok(root, "drop", ids["st2"], "--reason", "fora")
        out = st_ok(root, "close", ids["story"], "--summary", "story da Ana encerrada")
        self.assertRegex(out, GIT_ADD)

    def test_ca09_close_de_sprint_orienta_git_add(self):
        root, ids = fresh("ca09d")
        spr = new_id(root, "sprint", "--meta", "sprint curta da Ana")
        st_ok(root, "start", spr)
        t = new_id(root, "task", *_us("Frete da Ana", "src/billing/frete.py", "--sprint", spr))
        st_ok(root, "drop", t, "--reason", "nao precisa")
        out = st_ok(root, "close", spr, "--summary", "encerrada")
        self.assertRegex(out, GIT_ADD)

    def test_ca09_controle_close_continua_movendo_para_archive(self):
        root, ids = fresh("ca09e")
        st_ok(root, "drop", ids["st1"], "--reason", "fora")
        st_ok(root, "drop", ids["st2"], "--reason", "fora")
        st_ok(root, "close", ids["story"], "--summary", "ok")
        self.assertEqual(item(root, ids["story"])[0], "archive")


if __name__ == "__main__":
    unittest.main()
