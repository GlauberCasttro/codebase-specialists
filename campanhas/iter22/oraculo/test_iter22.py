"""ORÁCULO campanha-iter22 (0.12.1) — `cs-state show` barrado pelo guard (uso real) e a varredura argparse × guard.

Mapa requisito → teste e critérios em ESPEC.md (mesma pasta). Resumo:

  CA-01  agente PRINCIPAL roda `.swarm/bin/cs-state show <id>` PELO hook pre-bash do alvo ⇒ guard libera (exit 0,
         sem "desconhecido") e o comando imprime a task em Markdown com o id e o título.
  CA-02  SUBAGENTE (payload com agent_id/agent_type) em delegação roda o mesmo `show` ⇒ liberado; subcomandos que
         MUDAM estado (`close`, `new`, `start`) continuam barrados para o subagente (R).
  CA-03  todo subcomando de nível superior do argparse do cs-state INSTALADO no alvo tem regra no guard: rodando o
         guard real com o payload do principal para cada um, nenhum devolve "desconhecido". Calibração: um subcomando
         fictício acrescentado ao argparse (numa cópia da skill) sem regra faz este teste falhar.
  CA-04  VERSION ≥ 0.12.1; o catálogo references/migrations.json5 tem `to: "0.12.1"` com a ação `harness`; alvo
         0.12.0 REAL (skill extraída por `git archive` do commit da 0.12.0) → `cs.py upgrade` lista 0.12.1, o
         `--apply` reinstala o guard e o `show` passa pelo hook; a docstring de `notebook_text_problems` não afirma
         mais que bloco desatualizado com selo íntegro é aceito.

Comportamento observável: CLIs reais em subprocesso (`cs.py`, `.swarm/harness/guard.py` e `.swarm/bin/cs-state`
instalados no alvo). Versão sempre RELATIVA (≥), nunca ==.
Skill sob teste: $CS_SKILL_DIR, senão a raiz deste projeto. Skill 0.12.0: $CS_OLD_SKILL_DIR, senão
`git archive 7fdb431` deste repositório. Temporários: $CS_ORACLE_TMP (padrão: o tempdir do Python).
Python 3.9+, unittest puro, só stdlib. Rodar (desta pasta): python3 -m unittest -v test_iter22
"""
import ast
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
OLD_COMMIT = "7fdb431"          # "0.12.0: memória dos agentes que não esquece (iter21)"
OLD_VERSION = "0.12.0"
NEW_VERSION = (0, 12, 1)

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x"}
SD = ".swarm"
AGENT = "dev-billing"
VERIFY = "python3 -m unittest tests.test_ok"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_ok"
TITLE = "Aplicar cupom da Ana"
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
SUBS_RE = re.compile(r"\{([a-z0-9_,-]+)\}")

_TMP = {}


# ================================================================================================ infraestrutura
def _env(extra=None):
    e = dict(os.environ)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "CS_GUARD_OFF", "CS_ROOT", "CS_SKILL_VERSION_FILE",
              "CS_MIGRATIONS_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(GIT_ENV)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
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


def bash(root, cmd):
    """Roda o comando como o agente rodaria no Bash do alvo (depois de o hook liberar)."""
    return _run(["bash", "-c", cmd], root)


def hook_bash(root, cmd, actor=None):
    """Hook pre-bash REAL do alvo: `.swarm/harness/guard.py pre-bash` com o payload da ferramenta Bash."""
    payload = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": cmd}, "cwd": root,
               "session_id": "s-iter22"}
    payload.update(actor or {})
    return _run([sys.executable, os.path.join(root, SD, "harness", "guard.py"), "pre-bash"], root, timeout=120,
                extra={"CLAUDE_PROJECT_DIR": root}, stdin=json.dumps(payload).encode())


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


def _base_tmp():
    if "base" not in _TMP:
        _TMP["base"] = tempfile.mkdtemp(prefix="oraculo-iter22-", dir=os.environ.get("CS_ORACLE_TMP") or None)
    return _TMP["base"]


def tearDownModule():
    if "base" in _TMP:
        shutil.rmtree(_TMP["base"], ignore_errors=True)


def old_skill():
    """A skill 0.12.0 real: $CS_OLD_SKILL_DIR ou `git archive` do commit da 0.12.0 deste projeto (sem escrever no repo)."""
    if "old" in _TMP:
        return _TMP["old"]
    d = os.environ.get("CS_OLD_SKILL_DIR")
    if not d:
        d = os.path.join(_base_tmp(), "skill-0.12.0")
        p = subprocess.run(["git", "-C", PROJECT, "archive", "--format=tar", OLD_COMMIT], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300)
        if p.returncode != 0:
            raise AssertionError("não consegui extrair a skill 0.12.0 (git archive %s): %s — defina $CS_OLD_SKILL_DIR"
                                 % (OLD_COMMIT, p.stderr.decode()))
        os.makedirs(d)
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(d, filter="data")
            else:
                tf.extractall(d)
    d = os.path.realpath(d)
    v = read_text(os.path.join(d, "VERSION")).strip()
    if v != OLD_VERSION:
        raise AssertionError("skill antiga em %s tem VERSION %s (esperado %s)" % (d, v, OLD_VERSION))
    _TMP["old"] = d
    return d


def make_target(skill, name):
    """Repo da fixture do emit (dev-billing, dev-web, reviewer, qa); init + harness install + emit pela skill dada;
    estado iniciado e UMA task avulsa (dev-billing) criada pelo motor instalado. Devolve (raiz, id da task)."""
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
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    cs_ok(skill, dest, "init", "--platforms", "claude-code")
    cs_ok(skill, dest, "harness", "install", "--allow-outside")
    cs_ok(skill, dest, "emit", "--allow-outside")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "gerado pela skill")
    st_ok(dest, "init")
    out = st_ok(dest, "new", "task", "--tipo", "US", "--agent", AGENT, "--title", TITLE, "--avulsa",
                "--allowed-path", "src/billing/coupons.py", "--verify-cmd", VERIFY, "--como", "cliente",
                "--quero", "cupom", "--para", "pagar menos", "--criterio", C1)
    got = CREATED_RE.findall(out)
    if not got:
        raise AssertionError("`new` deveria imprimir `criado <ID> em <path>`: %r" % out)
    for need in (os.path.join(SD, "harness", "guard.py"), os.path.join(SD, "bin", "cs-state")):
        if not os.path.exists(os.path.join(dest, need)):
            raise AssertionError("fixture: %s ausente no alvo" % need)
    return dest, got[0][0]


def target():
    if "target" not in _TMP:
        _TMP["target"] = make_target(SKILL, "alvo")
    return _TMP["target"]


def subcommands(root):
    """Subcomandos de nível superior do argparse do cs-state INSTALADO (lidos do `--help`, não de lista interna)."""
    code, out, err = st(root, "--help")
    if code != 0:
        raise AssertionError("cs-state --help → %d: %s%s" % (code, out, err))
    m = SUBS_RE.search(out)
    if not m:
        raise AssertionError("cs-state --help sem a lista {sub,...}: %r" % out[:600])
    subs = [s for s in m.group(1).split(",") if s]
    if len(subs) < 40 or "show" not in subs:
        raise AssertionError("argparse do cs-state com lista inesperada: %r" % subs)
    return subs


def assert_unblocked(tc, res, what):
    code, out, err = res
    tc.assertNotIn("desconhecido", out + err, "%s: guard respondeu 'desconhecido': %s" % (what, (out + err)[-600:]))
    tc.assertEqual(code, 0, "%s: o hook pre-bash deveria liberar (exit 0), deu %d: %s" % (what, code, (out + err)[-600:]))


def assert_show_markdown(tc, root, tid):
    code, out, err = bash(root, "%s/bin/cs-state show %s" % (SD, tid))
    tc.assertEqual(code, 0, "cs-state show %s → %d: %s%s" % (tid, code, out, err))
    tc.assertRegex(out, r"(?m)^#+ .*%s" % re.escape(tid), "show deveria ter título Markdown com o id: %r" % out[:600])
    tc.assertIn(TITLE, out)


SUB_ACTOR = {"agent_id": "ag-iter22", "agent_type": AGENT}


# ================================================================================================ CA-01
class TestCA01(unittest.TestCase):
    def test_ca01_principal_show_pelo_hook_liberado_e_imprime_markdown(self):
        root, tid = target()
        cmd = "%s/bin/cs-state show %s" % (SD, tid)
        assert_unblocked(self, hook_bash(root, cmd), "principal: " + cmd)
        assert_show_markdown(self, root, tid)

    def test_ca01_principal_board_continua_liberado_controle(self):
        root, _ = target()
        assert_unblocked(self, hook_bash(root, "%s/bin/cs-state board" % SD), "principal: cs-state board")


# ================================================================================================ CA-02
class TestCA02(unittest.TestCase):
    def test_ca02_subagente_show_pelo_hook_liberado(self):
        root, tid = target()
        cmd = "%s/bin/cs-state show %s" % (SD, tid)
        assert_unblocked(self, hook_bash(root, cmd, SUB_ACTOR), "subagente: " + cmd)
        assert_show_markdown(self, root, tid)

    def test_ca02_subagente_mutacao_continua_barrada(self):
        root, tid = target()
        for cmd in ("%s/bin/cs-state close %s --summary x" % (SD, tid),
                    "%s/bin/cs-state start %s" % (SD, tid),
                    "%s/bin/cs-state new task --tipo FIX --avulsa --title x" % SD):
            code, out, err = hook_bash(root, cmd, SUB_ACTOR)
            self.assertEqual(code, 2, "subagente não pode mudar estado (%s): %d %s%s" % (cmd, code, out, err))


# ================================================================================================ CA-03
class TestCA03(unittest.TestCase):
    def test_ca03_todo_subcomando_do_argparse_tem_regra_no_guard(self):
        root, _ = target()
        sem_regra = []
        for sub in subcommands(root):
            code, out, err = hook_bash(root, "%s/bin/cs-state %s" % (SD, sub))
            if "desconhecido" in out + err:
                sem_regra.append(sub)
        self.assertEqual(sem_regra, [], "subcomandos do argparse sem regra no guard (o principal recebe "
                                        "'desconhecido'): %s" % sem_regra)


# ================================================================================================ CA-04
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


def catalog():
    return _strip_json5(read_text(os.path.join(SKILL, "references", "migrations.json5")))


def notebook_doc():
    src = read_text(os.path.join(SKILL, "scripts", "harness", "engine", "guard.py"))
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == "notebook_text_problems":
            return ast.get_docstring(node) or ""
    raise AssertionError("notebook_text_problems não encontrada em guard.py")


def upgraded():
    if "up" not in _TMP:
        root, tid = make_target(old_skill(), "alvo-0.12.0")
        r = {"root": root, "tid": tid}
        r["guard_before"] = read_text(os.path.join(root, SD, "harness", "guard.py"))
        r["hook_before"] = hook_bash(root, "%s/bin/cs-state show %s" % (SD, tid))
        r["plan"] = cs(SKILL, root, "upgrade")
        r["apply"] = cs(SKILL, root, "upgrade", "--apply", "--allow-outside")
        _TMP["up"] = r
    return _TMP["up"]


class TestCA04(unittest.TestCase):
    def test_ca04_version_e_catalogo_0121_com_harness(self):
        v = read_text(os.path.join(SKILL, "VERSION")).strip()
        self.assertGreaterEqual(vtuple(v), NEW_VERSION, "VERSION %s < 0.12.1" % v)
        cat = catalog()
        self.assertGreaterEqual(vtuple(cat.get("version", "0.0.0")), NEW_VERSION)
        ents = [m for m in cat.get("migrations") or [] if str(m.get("to")) == "0.12.1"]
        self.assertEqual(len(ents), 1, "catálogo deveria ter exatamente uma entrada to: 0.12.1")
        kinds = [a.get("kind") for a in ents[0].get("actions") or []]
        self.assertIn("harness", kinds, "a 0.12.1 precisa reinstalar o motor (ação harness): %s" % kinds)

    def test_ca04_upgrade_de_alvo_0120_lista_0121_e_libera_show(self):
        r = upgraded()
        code, out, err = r["plan"]
        self.assertEqual(code, 0, out + err)
        self.assertIn("0.12.1", out + err, "o plano do upgrade deveria listar a 0.12.1: %s" % (out + err)[-1500:])
        code, out, err = r["apply"]
        self.assertEqual(code, 0, "upgrade --apply → %d: %s%s" % (code, out[-2000:], err[-2000:]))
        guard_after = read_text(os.path.join(r["root"], SD, "harness", "guard.py"))
        self.assertNotEqual(guard_after, r["guard_before"], "o apply deveria reinstalar o guard do alvo")
        assert_unblocked(self, hook_bash(r["root"], "%s/bin/cs-state show %s" % (SD, r["tid"])),
                         "alvo atualizado: show")
        assert_show_markdown(self, r["root"], r["tid"])

    def test_ca04_alvo_0120_show_barrado_antes_controle(self):
        # a fixture reproduz o defeito do uso real: na 0.12.0 o hook barra o show do principal
        code, out, err = upgraded()["hook_before"]
        self.assertEqual(code, 2, out + err)
        self.assertIn("desconhecido", out + err)

    def test_ca04_docstring_do_caderno_nao_aceita_bloco_desatualizado(self):
        doc = " ".join(notebook_doc().split())
        low = doc.lower()
        self.assertNotRegex(low, r"desatualizad\w*\s+mas\s+com\s+selo\s+[íi]ntegro\s+tamb[ée]m\s+n[ãa]o",
                            "a docstring ainda afirma que bloco desatualizado com selo íntegro é aceito: %r" % doc)
        for sent in re.split(r"(?<=[.;:—])\s+|\(|\)", low):
            if "desatualizad" in sent:
                self.assertRegex(sent, r"recus|bloque|problema|diverg|n[ãa]o (é |e )?aceit|rejeit|fail",
                                 "docstring cita bloco desatualizado sem dizer que é recusado: %r" % sent)


if __name__ == "__main__":
    unittest.main()
