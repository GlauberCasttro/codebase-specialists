"""iter19 (B-14, task 05) — ação `state-format` do `cs.py upgrade`: plano sem escrita, apply converte o estado de um
alvo 0.10.1 REAL (git archive 97a1718) em .json por UM evento encadeado que só anexa, 2ª execução sem mudança, commit
pelo pre-commit sem --no-verify, validate antes reprovado aborta sem escrever, OWN_RESIDUE com selftest.json.

O catálogo real só ganha a 0.11.0 na task 06: aqui um catálogo TEMPORÁRIO ($CS_MIGRATIONS_FILE, cópia do real + a
entrada 0.11.0) e uma VERSION temporária ($CS_SKILL_VERSION_FILE). Pessoa = "Ana". Sem alvo antigo, os testes se pulam."""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(_HERE))
SKILL = os.path.dirname(SCRIPTS)
HARNESS_TESTS = os.path.join(SCRIPTS, "harness", "tests")
for _p in (SCRIPTS, HARNESS_TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_iter19_estado as T  # noqa: E402  (monta o alvo 0.10.1 real; só a função, não os casos)
from upgrade import core as C  # noqa: E402

ENTRY = ('  ,{\n   to: "0.11.0",\n   why: "estado em JSON legivel (teste)",\n   actions: [\n    {kind: "harness"},\n'
         '    {kind: "emit"},\n    {kind: "state-format"}\n   ]\n  }\n')
_ENV = {}


def _base():
    if "dir" not in _ENV:
        _ENV["dir"] = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter19-t05-"))
    return _ENV["dir"]


def tearDownModule():
    if "dir" in _ENV:
        shutil.rmtree(_ENV["dir"], ignore_errors=True)
    T.tearDownModule()


def temp_env():
    """{CS_MIGRATIONS_FILE, CS_SKILL_VERSION_FILE}: catálogo real + 0.11.0 com state-format, VERSION 0.11.0."""
    if "env" not in _ENV:
        with open(os.path.join(SKILL, "references", "migrations.json5"), encoding="utf-8") as fh:
            txt = fh.read()
        if '"0.11.0"' in txt:        # a task 06 já cadastrou: usa o real
            cat = os.path.join(SKILL, "references", "migrations.json5")
        else:
            txt = txt.replace('version: "0.10.1"', 'version: "0.11.0"', 1)
            i = txt.rindex("\n ]\n}")
            txt = txt[:i].rstrip("\n") + "\n" + ENTRY + txt[i + 1:]
            cat = os.path.join(_base(), "migrations.json5")
            with open(cat, "w", encoding="utf-8") as fh:
                fh.write(txt)
        # a VERSION acompanha o catálogo usado (a skill corrente pode já estar acima da 0.11.0, ex.: 0.12.0)
        m = re.search(r'^\s*version:\s*"([^"]+)"', txt, re.M)
        ver = os.path.join(_base(), "VERSION")
        with open(ver, "w", encoding="utf-8") as fh:
            fh.write((m.group(1) if m else "0.11.0") + "\n")
        _ENV["env"] = {"CS_MIGRATIONS_FILE": cat, "CS_SKILL_VERSION_FILE": ver}
    return _ENV["env"]


def cs(root, *args):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **T._GIT_ENV)
    for k in ("CLAUDE_PROJECT_DIR", "CS_ACTOR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e.update(temp_env())
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cs.py"), "--target", root] + list(args), cwd=root,
                       env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def sd(root, rel):
    return os.path.join(root, ".swarm", rel)


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def keep(snap):
    return {k: v for k, v in snap.items() if not k.startswith(".swarm/backups/") and ".git" not in k.split(os.sep)
            and not k.endswith("harness-ledger.jsonl") and not k.startswith(".swarm/.engine/evidence")}


class Base(unittest.TestCase):
    def copy(self, name):
        return T._copy_old(name)


class TestStateFormatUpgrade(Base):
    @classmethod
    def setUpClass(cls):
        tpl = T.build_old_target()
        if tpl is None:
            raise unittest.SkipTest("skill 0.10.1 indisponível")
        cls.root = T._copy_old("t05-aplicado")
        cls.before_files = T._state_files(cls.root)
        cls.olds = [p for p in cls.before_files if p.endswith(".json5")]
        cls.events_before = read(sd(cls.root, "events.jsonl"))
        cls.snap0 = T._snap(cls.root)
        cls.plan = cs(cls.root, "upgrade")
        cls.snap_plan = T._snap(cls.root)
        cls.apply = cs(cls.root, "upgrade", "--apply", "--allow-outside")

    def test_alvo_de_partida_0101_em_json5(self):
        self.assertGreaterEqual(len(self.olds), 8, self.before_files)

    def test_plano_lista_json_e_nao_escreve(self):
        code, out, err = self.plan
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.snap_plan, self.snap0, "o plano não escreve")
        self.assertIn("0.11.0 — ", out)
        self.assertRegex(out, r"(?i)\bjson\b")
        self.assertIn("state-format", out)
        for old in self.olds:
            self.assertIn(old, out, "o plano mostra o par %s → .json" % old)
        self.assertIn(".json5 →", out)

    def test_apply_converte_todo_o_estado(self):
        code, out, err = self.apply
        self.assertEqual(code, 0, out + err)
        after = [p for p in T._state_files(self.root) if not p.endswith("selftest.json")]   # selftest: do VERIFY
        self.assertEqual([p for p in after if p.endswith(".json5")], [], after)
        self.assertEqual(sorted(p[:-1] for p in self.olds), after)
        self.assertIn("harness validate --strict antes", out)
        self.assertIn("migrate state-format", out)

    def test_um_evento_novo_e_antigos_prefixo_byte_a_byte(self):
        self.assertEqual(self.apply[0], 0, self.apply[1] + self.apply[2])
        now = read(sd(self.root, "events.jsonl"))
        self.assertTrue(now.startswith(self.events_before), "eventos antigos reescritos")
        new = [ln for ln in now[len(self.events_before):].split(b"\n") if ln.strip()]
        self.assertEqual(len(new), 1)
        rec = json.loads(new[0].decode("utf-8"))
        self.assertEqual(rec["type"], "arvore.format")

    def test_memoria_e_config_intactas(self):
        self.assertEqual(self.apply[0], 0)
        now = T._snap(self.root)
        for k, v in self.snap0.items():
            if "/.swarm/memory/" in "/" + k or "/memory/" in k or k.endswith("team.json5"):
                self.assertEqual(now.get(k), v, k)

    def test_segunda_execucao_nao_muda_nada(self):
        self.assertEqual(self.apply[0], 0)
        d = os.path.join(T._old_base(), "t05-idem")
        shutil.copytree(self.root, d, symlinks=True)
        before = keep(T._snap(d))
        code, out, err = cs(d, "upgrade", "--apply", "--allow-outside")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(keep(T._snap(d)), before, "2ª execução mudou algo")
        code, out, err = cs(d, "upgrade")
        self.assertNotRegex(out, r"(?m)^\s+0\.11\.0 — ")
        c2, o2 = T.st(d, "migrate", "state-format")
        self.assertIn("nada a migrar", o2)
        self.assertEqual(keep(T._snap(d)), before)

    def test_commit_pelo_hook_sem_no_verify(self):
        self.assertEqual(self.apply[0], 0)
        d = os.path.join(T._old_base(), "t05-commit")
        shutil.copytree(self.root, d, symlinks=True)
        head = T._git(d, "rev-parse", "HEAD").strip()
        T._commit(d, "upgrade 0.11.0")        # sem --no-verify; asserta se o hook barrar
        self.assertNotEqual(T._git(d, "rev-parse", "HEAD").strip(), head)


class TestValidateAntesReprovado(Base):
    def setUp(self):
        if T.build_old_target() is None:
            self.skipTest("skill 0.10.1 indisponível")
        self.root = self.copy(self.id().split(".")[-1])

    def test_estado_corrompido_recusa_sem_escrever(self):
        with open(sd(self.root, "events.jsonl"), "ab") as fh:
            fh.write(b"isto nao e um evento\n")
        snap = T._snap(self.root)
        code, out, err = cs(self.root, "upgrade", "--apply", "--allow-outside")
        self.assertEqual(code, 3, out + err)
        self.assertIn("nada escrito", err)
        self.assertEqual(T._snap(self.root), snap, "recusou mas escreveu")

    def test_validate_antes_reprovado_aborta_antes_do_backup(self):
        """Motor aceita o dry-run mas `harness validate --strict` reprova: o apply recusa antes do backup."""
        env = temp_env()
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        real = C.run_cs

        def fake(target, argv, timeout=C.CMD_TIMEOUT):
            if list(argv[:2]) == ["harness", "validate"]:
                return 1, "validate: FALHOU\nFALHA x\n", ""
            return real(target, argv, timeout)
        snap = T._snap(self.root)
        C.run_cs = fake
        err = io.StringIO()
        real_err, sys.stderr = sys.stderr, err
        try:
            code = C.apply(self.root, allow_outside=True, out=io.StringIO())
        finally:
            C.run_cs, sys.stderr = real, real_err
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual(code, 3, err.getvalue())
        self.assertIn("validate --strict", err.getvalue())
        self.assertIn("state-format", err.getvalue())
        self.assertEqual(T._snap(self.root), snap, "escreveu apesar do validate reprovado")


class TestFalhaDaAcaoRestaura(Base):
    def test_falha_do_motor_restaura_o_backup(self):
        if T.build_old_target() is None:
            self.skipTest("skill 0.10.1 indisponível")
        root = self.copy("t05-falha")
        env = temp_env()
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        real = C._state_format_cmd

        def fake(r, dry):
            if dry:
                return real(r, dry)
            return 1, "", "RECUSADO: simulado"
        snap = keep(T._snap(root))
        C._state_format_cmd = fake
        err, out = io.StringIO(), io.StringIO()
        real_err, sys.stderr = sys.stderr, err
        try:
            code = C.apply(root, allow_outside=True, out=out)
        finally:
            C._state_format_cmd, sys.stderr = real, real_err
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual(code, 1, out.getvalue() + err.getvalue())
        self.assertIn("backup restaurado", err.getvalue())
        self.assertEqual(keep(T._snap(root)), snap, "o estado não voltou ao que era")


class TestPreservadosAnexo(unittest.TestCase):
    def _target(self, data):
        d = tempfile.mkdtemp(prefix="cs-t05-ev-", dir=_base())
        os.makedirs(os.path.join(d, ".swarm"))
        with open(os.path.join(d, ".swarm", "events.jsonl"), "wb") as fh:
            fh.write(data)
        return d

    def test_append_aceito(self):
        d = self._target(b'{"seq":0}\n{"seq":1}\n')
        snap = C.events_snapshot(d)
        with open(os.path.join(d, ".swarm", "events.jsonl"), "ab") as fh:
            fh.write(b'{"seq":2}\n')
        self.assertIsNone(C.events_append_violation(snap, d))

    def test_reescrita_truncamento_e_remocao_barrados(self):
        d = self._target(b'{"seq":0}\n{"seq":1}\n')
        snap = C.events_snapshot(d)
        p = os.path.join(d, ".swarm", "events.jsonl")
        with open(p, "wb") as fh:
            fh.write(b'{"seq":9}\n{"seq":1}\n{"seq":2}\n')
        self.assertIn("reescritos", C.events_append_violation(snap, d))
        with open(p, "wb") as fh:
            fh.write(b'{"seq":0}\n')
        self.assertIn("reescritos", C.events_append_violation(snap, d))
        os.remove(p)
        self.assertIn("sumiu", C.events_append_violation(snap, d))

    def test_state_format_e_acao_explicita_e_kind_valido(self):
        from upgrade import version as V
        self.assertIn("state-format", V.KINDS)
        self.assertIn("state-format", C.EXPLICIT_KINDS)
        self.assertIn("state-format", C.ORDER)
        errs = V.validate_catalog({"version": "0.11.0", "migrations": [
            {"to": "0.11.0", "why": "x", "actions": [{"kind": "state-format", "x": 1}]}]})
        self.assertTrue(any("state-format não aceita parâmetros" in e for e in errs), errs)
        self.assertEqual(V.validate_catalog({"version": "0.11.0", "migrations": [
            {"to": "0.11.0", "why": "x", "actions": [{"kind": "state-format"}]}]}), [])


class TestOwnResidueJson(unittest.TestCase):
    def test_selftest_json_e_json5_sao_residuo_proprio(self):
        d = tempfile.mkdtemp(prefix="cs-t05-res-", dir=_base())
        for rel in ("state/selftest.json", ".engine/selftest.json", "state/selftest.json5"):
            full = os.path.join(d, ".swarm", rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
        got = C.own_residue(d)
        self.assertEqual(got, sorted([os.path.join(".engine", "selftest.json"), os.path.join("state", "selftest.json"),
                                      os.path.join("state", "selftest.json5")]))

    def test_outro_arquivo_continua_barrando(self):
        d = tempfile.mkdtemp(prefix="cs-t05-res2-", dir=_base())
        os.makedirs(os.path.join(d, ".swarm", "state"))
        for rel in ("selftest.json", "outra.json"):
            with open(os.path.join(d, ".swarm", "state", rel), "w") as fh:
                fh.write("{}")
        self.assertIsNone(C.own_residue(d))


if __name__ == "__main__":
    unittest.main()
