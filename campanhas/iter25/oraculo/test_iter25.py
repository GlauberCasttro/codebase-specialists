"""ORÁCULO campanha-iter25 (hotfix 0.13.1) — `status` gravado no arquivo de cada item da árvore.

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Tudo pelo caminho REAL: alvo da fixture do emit
(init + harness install + emit pela skill), estado em MODO ÁRVORE (`cs-state init`), comandos pelo `cs-state` do
próprio alvo (`.swarm/harness/state.py --root <alvo>`, o que `.swarm/bin/cs-state` chama). O status DERIVADO vem do
MESMO motor que gravou: `tree.status_of(tree.load_view(alvo), item)` importado de `<alvo>/.swarm/harness/` num
subprocesso (nunca o motor da skill do oráculo).

  CA-01  épico/sprint/feature/story/task (sprint e backlog): `status` no arquivo == CANON(derivado) (+ literais en,
         D-37: TODO/BACKLOG/ACTIVE/DONE/DROPPED; `<M2>/<despacho>` igual); a exibição continua em português.
  CA-02  start, dispatch, submit, verify, review, accept: depois de CADA comando, arquivo == CANON(derivado).
  CA-03  drop ⇒ archive DROPPED (exibe "descartada"/"descartado"); close ⇒ DONE ("fechada"/"fechado").
  CA-04  `status` trocado à mão ⇒ `validate --strict` ≠ 0 citando item e valor certo (código en);
         valor fora do vocabulário (ex. "a fazer" gravado) acusado; sem edição ⇒ 0.
  CA-05  alvo 0.13.0 real (`git archive 3eed3b4` ou $CS_OLD_SKILL_DIR): upgrade grava `status` em TODOS os itens,
         nenhum outro campo muda, events.jsonl idêntico (bytes), validate ok, 2º apply idempotente, VERSION ≥ 0.13.1.

Versão sempre RELATIVA (≥). Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Temporários: $CS_ORACLE_TMP,
senão o TMPDIR do sistema. Python 3.9+, unittest, só stdlib. Rodar (desta pasta): python3 -m unittest -v test_iter25
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
OLD_COMMIT = "3eed3b4"          # estado com a skill 0.13.0 (iter23 entregue)
OLD_VERSION = (0, 13, 0)
NEW_VERSION = (0, 13, 1)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
VERIFY = "python3 -m unittest tests.test_ok"
ACEITE = "python3 -m unittest tests.test_red"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
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


def new_id(root, *args):
    out = st_ok(root, "new", *args)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    return got[0][0]


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
                if isinstance(d, dict) and d.get("id"):
                    if d["id"] in got:
                        raise AssertionError("item %s com 2 arquivos: %s e %s" % (d["id"], got[d["id"]][1], p))
                    got[d["id"]] = (zone, p, d)
    return got


def item(root, iid):
    got = all_items(root)
    if iid not in got:
        raise AssertionError("item %s sem arquivo na árvore" % iid)
    return got[iid]


def disk(root, iid):
    return item(root, iid)[2].get("status")


DERIVE = ("import sys, json; sys.dont_write_bytecode = True; root = sys.argv[1]; "
          "sys.path.insert(0, root + '/.swarm/harness'); import tree; tv = tree.load_view(root); "
          "print(json.dumps({i: tree.status_of(tv, it) for i, it in tv.items.items()}))")


def derived_all(root):
    """status de cada item calculado pelo motor DO ALVO (o mesmo que grava)."""
    code, out, err = _run([sys.executable, "-c", DERIVE, root], root)
    if code != 0:
        raise AssertionError("tree.status_of do alvo falhou: %s%s" % (out, err))
    return json.loads(out.strip().splitlines()[-1])


def derived(root, iid):
    return derived_all(root)[iid]


# D-37 (mudança oficial 01): o `status` GRAVADO no arquivo é o código canônico em inglês; a exibição
# (`tree.status_of`, board/next/show) continua em português. Mapa definido AQUI, no oráculo (não no produto).
CANON_MAP = {"a fazer": "TODO", "backlog": "BACKLOG", "ativo": "ACTIVE", "fechada": "DONE", "fechado": "DONE",
             "descartada": "DROPPED", "descartado": "DROPPED"}
CANON_VOCAB = {"TODO", "BACKLOG", "ACTIVE", "DONE", "DROPPED"}


def CANON(shown):
    """exibição pt → código gravado en; `<M2>/<despacho>` (já inglês) fica igual; desconhecido → None (falha)."""
    if shown in CANON_MAP:
        return CANON_MAP[shown]
    if isinstance(shown, str) and "/" in shown:
        return shown
    return None


def mismatches(root, ids=None):
    """['ID: arquivo=X esperado=CANON(derivado)'] — vazio quando o arquivo de todos os itens tem `status` canônico."""
    der = {k: CANON(v) for k, v in derived_all(root).items()}
    items = all_items(root)
    bad = []
    for iid in sorted(ids or der):
        f = items.get(iid, (None, None, {}))[2].get("status")
        if f != der.get(iid):
            bad.append("%s: arquivo=%r esperado=%r" % (iid, f, der.get(iid)))
    return bad


def snap(root):
    """{rel: bytes} dos arquivos de item + events.jsonl."""
    s = {}
    base = os.path.join(root, SD)
    for zone in ("backlog", "state", "archive"):
        for dp, _, fns in os.walk(os.path.join(base, zone)):
            for fn in fns:
                p = os.path.join(dp, fn)
                with open(p, "rb") as f:
                    s[os.path.relpath(p, root)] = f.read()
    return s


def events_bytes(root):
    p = os.path.join(root, SD, "events.jsonl")
    with open(p, "rb") as f:
        return f.read()


# ================================================================================================ fixtures
def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = os.path.realpath(tempfile.mkdtemp(prefix="oraculo-iter25-",
                                                         dir=os.environ.get("CS_ORACLE_TMP") or None))
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP and not os.environ.get("CS_ORACLE_KEEP"):
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.13.0 real: $CS_OLD_SKILL_DIR ou `git archive` do commit (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-antiga")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.13.0 (git archive %s): %s — defina $CS_OLD_SKILL_DIR"
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
        raise AssertionError("skill antiga em %s tem VERSION %s (esperado 0.13.0)" % (d, v))
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
    for f in ("coupons.py", "pix.py", "frete.py", "taxa.py", "nota.py", "q.py"):
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
    return ["--tipo", "US", "--agent", AGENT, "--title", title, "--allowed-path", path, "--verify-cmd", VERIFY,
            "--como", "cliente", "--quero", "cupom", "--para", "pagar menos", "--criterio", C1] + list(extra)


def populate(root):
    """Árvore da Ana: EPC ativo › SPR ativa › FEA ativa (com story) + task direto na sprint; task no backlog."""
    ids = {}
    ids["epc"] = new_id(root, "epico", "--title", "Pagamentos da Ana", "--objetivo", "pix")
    ids["spr"] = new_id(root, "sprint", "--meta", "pix da Ana", "--epico", ids["epc"])
    st_ok(root, "start", ids["epc"])
    st_ok(root, "start", ids["spr"])
    ids["fea"] = new_id(root, "feature", "--title", "Pix da Ana", "--sprint", ids["spr"], "--aceite", ACEITE)
    st_ok(root, "start", ids["fea"])
    ids["story"] = new_id(root, "story", "--tipo", "US", "--title", "Story da Ana", "--feature", ids["fea"],
                          "--agents", AGENT, "--agents", "dev-web", "--allowed-path", "src/billing/q.py",
                          "--verify-cmd", VERIFY, "--como", "cliente", "--quero", "x", "--para", "y", "--criterio", C1)
    ids["task"] = new_id(root, "task", *_us("Cupom da Ana", "src/billing/coupons.py", "--sprint", ids["spr"]))
    ids["task2"] = new_id(root, "task", *_us("Taxa da Ana", "src/billing/taxa.py", "--sprint", ids["spr"]))
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


def run_m2(root, tid, steps):
    """Conduz o M2 até ACCEPTED como o oráculo iter10; chama steps(nome) depois de CADA comando."""
    st_ok(root, "start", tid)
    steps("start")
    st_ok(root, "dispatch", tid, "--manual", "--model", "sonnet")
    steps("dispatch")
    write(root, "src/billing/coupons.py", "X = 2\n")
    st_ok(root, "submit", tid, "--files-changed", "src/billing/coupons.py", "--check", "unittest: OK", "--risk",
          "nenhum", "--handoff-notes", "ok", actor=AGENT)
    steps("submit")
    st_ok(root, "verify", tid)
    steps("verify")
    st_ok(root, "review", tid, "--by", "reviewer", "--verdict", "PASS", "--findings", "conferido: teste verde")
    steps("review")
    st_ok(root, "accept", tid)
    steps("accept")


# ================================================================================================ CA-01
class TestCA01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.ids = fresh("ca01")

    def test_ca01_status_no_arquivo_igual_ao_derivado(self):
        bad = mismatches(self.root, [self.ids[k] for k in ("epc", "spr", "fea", "story", "task", "task2", "bkl")])
        self.assertEqual(bad, [], "o arquivo de cada item deveria ter `status` == CANON(tree.status_of):\n  "
                         + "\n  ".join(bad))

    def test_ca01_literais_no_arquivo(self):
        want = {"epc": "ACTIVE", "spr": "ACTIVE", "fea": "ACTIVE", "task": "TODO", "task2": "TODO",
                "bkl": "BACKLOG"}
        bad = ["%s (%s): arquivo=%r esperado=%r" % (self.ids[k], k, disk(self.root, self.ids[k]), v)
               for k, v in sorted(want.items()) if disk(self.root, self.ids[k]) != v]
        self.assertEqual(bad, [], "literais de `status` no arquivo:\n  " + "\n  ".join(bad))

    def test_ca01_controle_derivado_continua(self):
        """controle: a derivação de hoje (tree.status_of) dá os literais do CA — o oráculo compara com ela."""
        der = derived_all(self.root)
        want = {"epc": "ativo", "spr": "ativo", "fea": "ativo", "task": "a fazer", "bkl": "backlog"}
        for k, v in want.items():
            self.assertEqual(der.get(self.ids[k]), v, "%s derivado" % k)

    def test_ca01_controle_exibicao_continua_em_portugues(self):
        """controle (D-37): só o dado gravado muda; board e show continuam exibindo em português."""
        code, out, err = st(self.root, "board")
        self.assertEqual(code, 0, out + err)
        tid = self.ids["task"]
        lines = [ln for ln in out.splitlines() if tid in ln]
        self.assertTrue(any("a fazer" in ln for ln in lines), "board deveria exibir %s 'a fazer': %s" % (tid, out))
        self.assertTrue(any("backlog" in ln for ln in out.splitlines() if self.ids["bkl"] in ln), out)
        self.assertNotIn("[TODO]", out, "board não deveria exibir o código en")
        code, out, err = st(self.root, "show", tid)
        self.assertEqual(code, 0, out + err)
        self.assertIn("a fazer", out, "show deveria exibir 'a fazer': %s" % out)


# ================================================================================================ CA-02
class TestCA02(unittest.TestCase):
    def test_ca02_status_acompanha_cada_transicao_m2(self):
        root, ids = fresh("ca02a")
        tid = ids["task"]
        bad = []

        def step(name):
            f, d = disk(root, tid), CANON(derived(root, tid))
            if f != d:
                bad.append("depois de %s: arquivo=%r esperado=%r" % (name, f, d))
        run_m2(root, tid, step)
        self.assertEqual(bad, [], "status de %s no arquivo deveria acompanhar o M2:\n  " % tid + "\n  ".join(bad))

    def test_ca02_so_o_status_mudou_regrava(self):
        """dispatch/verify/review/accept mudam só o M2 (board.tasks), não o item da projeção: o arquivo é regravado."""
        root, ids = fresh("ca02b")
        tid = ids["task"]
        seen = []

        def step(name):
            seen.append((name, disk(root, tid), CANON(derived(root, tid))))
        run_m2(root, tid, step)
        bad = ["%s: arquivo=%r esperado=%r" % s for s in seen if s[0] in ("dispatch", "verify", "review", "accept")
               and s[1] != s[2]]
        self.assertEqual(bad, [], "transição só de M2 deveria regravar o `status` do arquivo:\n  " + "\n  ".join(bad))

    def test_ca02_controle_derivado_muda_a_cada_passo(self):
        """controle: o derivado de fato muda no M2 (o teste acima não é vácuo) e outros itens seguem coerentes."""
        root, ids = fresh("ca02c")
        tid = ids["task"]
        seen = []
        run_m2(root, tid, lambda n: seen.append(derived(root, tid)))
        self.assertGreaterEqual(len(set(seen)), 4, "derivados vistos: %s" % seen)
        self.assertTrue(all("/" in s for s in seen), seen)


# ================================================================================================ CA-03
class TestCA03(unittest.TestCase):
    def test_ca03_drop_de_task_nao_iniciada_descartada(self):
        root, ids = fresh("ca03a")
        st_ok(root, "drop", ids["task2"], "--reason", "fora do escopo da Ana")
        zone, _, d = item(root, ids["task2"])
        self.assertEqual(zone, "archive")
        self.assertEqual((d.get("status"), derived(root, ids["task2"])), ("DROPPED", "descartada"))

    def test_ca03_close_de_task_aceita_fechada(self):
        root, ids = fresh("ca03b")
        run_m2(root, ids["task"], lambda n: None)
        st_ok(root, "close", ids["task"], "--summary", "entregue")
        zone, _, d = item(root, ids["task"])
        self.assertEqual(zone, "archive")
        self.assertEqual((d.get("status"), derived(root, ids["task"])), ("DONE", "fechada"))

    def test_ca03_drop_de_sprint_vazia_descartado(self):
        root, ids = fresh("ca03c")
        spr = new_id(root, "sprint", "--meta", "sprint vazia da Ana")
        st_ok(root, "drop", spr, "--reason", "nao vai acontecer")
        zone, _, d = item(root, spr)
        self.assertEqual(zone, "archive")
        self.assertEqual((d.get("status"), derived(root, spr)), ("DROPPED", "descartado"))

    def test_ca03_close_de_sprint_fechado(self):
        root, ids = fresh("ca03d")
        spr = new_id(root, "sprint", "--meta", "sprint curta da Ana")
        st_ok(root, "start", spr)
        t = new_id(root, "task", *_us("Frete da Ana", "src/billing/frete.py", "--sprint", spr))
        st_ok(root, "drop", t, "--reason", "nao precisa")
        st_ok(root, "close", spr, "--summary", "encerrada")
        zone, _, d = item(root, spr)
        self.assertEqual(zone, "archive")
        self.assertEqual((d.get("status"), derived(root, spr)), ("DONE", "fechado"))
        self.assertEqual(mismatches(root), [], "toda a árvore coerente depois dos fechamentos")


# ================================================================================================ CA-04
def _edit_status(path, new):
    txt = read_text(path)
    txt2, n = re.subn(r'("status"\s*:\s*)"[^"]*"', lambda m: m.group(1) + json.dumps(new), txt, count=1)
    if n != 1:
        raise AssertionError("o arquivo %s não tem `status` para editar" % path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt2)


class TestCA04(unittest.TestCase):
    def test_ca04_status_editado_a_mao_acusado(self):
        root, ids = fresh("ca04a")
        tid = ids["task"]
        _, path, d = item(root, tid)
        self.assertEqual(d.get("status"), "TODO", "pré-condição: o arquivo tem o status canônico certo")
        _edit_status(path, "DONE")
        code, out, err = st(root, "validate", "--strict")
        self.assertNotEqual(code, 0, "validate --strict deveria acusar o status editado à mão: %s" % out)
        txt = out + err
        lines = [ln for ln in txt.splitlines() if tid in ln]
        self.assertTrue(lines, "a saída deveria citar %s: %s" % (tid, txt[-1500:]))
        self.assertTrue(any("TODO" in ln for ln in lines) or "TODO" in txt,
                        "a saída deveria citar o valor certo 'TODO': %s" % txt[-1500:])

    def test_ca04_status_fora_do_vocabulario_acusado(self):
        """D-37: valor de exibição pt gravado no arquivo ("a fazer") não é código canônico ⇒ validate acusa."""
        root, ids = fresh("ca04c")
        tid = ids["task"]
        _, path, d = item(root, tid)
        self.assertIn(d.get("status"), CANON_VOCAB, "pré-condição: o arquivo tem código canônico")
        _edit_status(path, "a fazer")
        code, out, err = st(root, "validate", "--strict")
        self.assertNotEqual(code, 0, "validate --strict deveria acusar 'a fazer' gravado no arquivo: %s" % out)
        txt = out + err
        self.assertTrue([ln for ln in txt.splitlines() if tid in ln],
                        "a saída deveria citar %s: %s" % (tid, txt[-1500:]))
        self.assertIn("TODO", txt, "a saída deveria citar o valor certo 'TODO': %s" % txt[-1500:])

    def test_ca04_controle_sem_edicao_valida(self):
        root, ids = fresh("ca04b")
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, "sem edição o validate --strict sai 0: %s%s" % (out, err))
        run_m2(root, ids["task"], lambda n: None)
        st_ok(root, "drop", ids["task2"], "--reason", "fora")
        code, out, err = st(root, "validate", "--strict")
        self.assertEqual(code, 0, "depois do M2 e do drop o validate --strict sai 0: %s%s" % (out, err))


# ================================================================================================ CA-05
def legacy_base():
    """Alvo instalado pela skill 0.13.0 real, com itens em state/, backlog/ e archive/ (sem `status`)."""
    if "legacy" in _TMP:
        return _TMP["legacy"]
    root = make_target(old_skill(), "base-legado")
    ids = populate(root)
    st_ok(root, "start", ids["task"])
    st_ok(root, "drop", ids["task2"], "--reason", "fora do escopo da Ana")
    ids["spr_x"] = new_id(root, "sprint", "--meta", "sprint vazia da Ana")
    st_ok(root, "drop", ids["spr_x"], "--reason", "nao vai acontecer")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "itens da Ana")
    its = all_items(root)
    zones = {z for z, _, _ in its.values()}
    if zones != {"state", "backlog", "archive"}:
        raise AssertionError("fixture: esperava itens nas 3 zonas, achei %s" % zones)
    _TMP["legacy"] = (root, ids)
    return _TMP["legacy"]


def upgraded():
    if "up" not in _TMP:
        src, ids = legacy_base()
        root = clone(src, "base-legado-atualizado")
        r = {"root": root, "ids": ids, "items0": all_items(root), "ev0": events_bytes(root), "snap0": snap(root)}
        r["plan"] = cs(SKILL, root, "upgrade")
        r["snap_plan"] = snap(root)
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        r["items1"] = all_items(root)
        r["ev1"] = events_bytes(root)
        r["snap1"] = snap(root)
        r["apply2"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        r["snap2"] = snap(root)
        r["ev2"] = events_bytes(root)
        _TMP["up"] = r
    return _TMP["up"]


def _sem_status(d):
    d = dict(d)
    d.pop("status", None)
    return d


class TestCA05(unittest.TestCase):
    def test_ca05_version_e_catalogo_0131(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.13.1" % v)
        cat = _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.13.1"]
        self.assertEqual(len(ents), 1, "catálogo deveria ter exatamente uma entrada to: 0.13.1")

    def test_ca05_plano_lista_0131(self):
        r = upgraded()
        code, out, err = r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertIn("0.13.1", out + err, "o plano deveria listar a 0.13.1")
        self.assertEqual(r["snap_plan"], r["snap0"], "o plano não altera nada")

    def test_ca05_apply_grava_status_em_todos_os_itens(self):
        r = upgraded()
        self.assertEqual(r["apply"][0], 0, r["apply"][1][-1500:] + r["apply"][2][-1500:])
        self.assertEqual(set(r["items1"]), set(r["items0"]), "o upgrade não cria nem remove item")
        self.assertEqual(mismatches(r["root"]), [], "depois do upgrade todo item tem `status` == CANON(derivado)")
        zs = {z for z, _, _ in r["items1"].values()}
        self.assertEqual(zs, {"state", "backlog", "archive"})

    def test_ca05_apply_outros_campos_e_eventos_intacta(self):
        r = upgraded()
        self.assertEqual(r["apply"][0], 0, r["apply"][1][-1500:] + r["apply"][2][-1500:])
        bad = []
        for iid, (z, p, d) in sorted(r["items0"].items()):
            z1, p1, d1 = r["items1"][iid]
            if (z1, os.path.relpath(p1, r["root"])) != (z, os.path.relpath(p, r["root"])):
                bad.append("%s mudou de lugar: %s → %s" % (iid, p, p1))
            if _sem_status(d1) != _sem_status(d):
                ks = sorted(k for k in set(d) | set(d1) if k != "status" and d.get(k) != d1.get(k))
                bad.append("%s mudou campos além de status: %s" % (iid, ks))
        self.assertEqual(bad, [], "\n  ".join(bad))
        self.assertEqual(r["ev1"], r["ev0"], ".swarm/events.jsonl deveria ficar idêntico (bytes)")

    def test_ca05_validate_strict_continua_depois_do_upgrade(self):
        r = upgraded()
        code, out, err = st(r["root"], "validate", "--strict")
        self.assertEqual(code, 0, "validate --strict depois do upgrade: %s%s" % (out[-2000:], err[-2000:]))

    def test_ca05_segundo_apply_continua_idempotente(self):
        r = upgraded()
        self.assertEqual(r["apply2"][0], 0, r["apply2"][1][-1500:] + r["apply2"][2][-1500:])
        self.assertEqual(r["snap2"], r["snap1"], "o 2º apply não pode alterar item")
        self.assertEqual(r["ev2"], r["ev1"], "o 2º apply não pode alterar events.jsonl")

    def test_ca05_controle_fixture_sem_status(self):
        """controle: o alvo 0.13.0 da fixture tem itens nas 3 zonas e nenhum com `status`."""
        src, _ = legacy_base()
        its = all_items(src)
        self.assertEqual([i for i, (_, _, d) in its.items() if "status" in d], [])
        self.assertEqual({z for z, _, _ in its.values()}, {"state", "backlog", "archive"})


if __name__ == "__main__":
    unittest.main()
