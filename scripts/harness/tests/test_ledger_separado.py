"""Regressão G6 (iteração 1): cs.py (cslib.log) grava linhas sem cadeia em .swarm/state/ledger.jsonl;
o harness exigia cadeia desde a linha 0 NO MESMO arquivo → validate --strict nunca ficava verde num fluxo
normal. O ledger encadeado do harness é outro arquivo; o log de execução do cs.py não entra na cadeia."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CS = os.path.join(SCRIPTS, "cs.py")


class TestLedgerSeparado(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cs-ledger-")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        with open(os.path.join(self.root, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cs(self, *args):
        return subprocess.run([sys.executable, CS, "--target", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=300)

    def test_validate_strict_after_cs_commands(self):
        for argv in (["init"], ["stage", "load", "init"], ["stage", "check", "init.2", "--answer", "as 4"]):
            r = self.cs(*argv)
            self.assertEqual(r.returncode, 0, r.stdout.decode())
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".swarm", "state", "ledger.jsonl")))
        r = self.cs("harness", "install", "--no-makefile", "--allow-outside")
        self.assertEqual(r.returncode, 0, r.stdout.decode())
        # mais linhas do cs.py DEPOIS do install (fluxo normal: stage check/done continuam logando)
        self.assertEqual(self.cs("stage", "load", "init").returncode, 0)
        r = self.cs("harness", "validate", "--strict", "--allow-empty")
        self.assertEqual(r.returncode, 0, r.stdout.decode())
        # e o ledger encadeado do harness continua detectando edição manual
        import importlib
        sys.path.insert(0, os.path.join(SCRIPTS, "harness", "engine"))
        hcore = importlib.import_module("hcore")
        hl = hcore.state_paths(self.root)["ledger"]
        self.assertNotEqual(os.path.basename(hl), "ledger.jsonl")
        hcore.ledger_append(self.root, {"kind": "block", "reason": "teste"})
        hcore.ledger_append(self.root, {"kind": "block", "reason": "teste 2"})
        self.assertEqual(self.cs("harness", "validate", "--strict", "--allow-empty").returncode, 0)
        with open(hl) as fh:
            lines = fh.readlines()
        with open(hl, "w") as fh:
            fh.writelines(lines[1:])
        r = self.cs("harness", "validate", "--strict", "--allow-empty")
        self.assertEqual(r.returncode, 1, r.stdout.decode())


if __name__ == "__main__":
    unittest.main()
