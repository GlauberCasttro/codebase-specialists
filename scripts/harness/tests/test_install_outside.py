"""Iteração 4 — `harness install` escrevia FORA de .swarm/ (.claude/settings.json, .claude/hooks/cs-guard.sh,
specialists.mk, bloco no Makefile, .git/hooks/pre-commit) sem mostrar a lista e sem `--allow-outside` (nos 3 alvos
da iteração 3 o usuário só soube depois). Agora: `--dry-run` lista o bloco `outside` e nada escreve; escrever fora
exige `--allow-outside` (igual ao `emit`); reinstalar sem mudança fora não pede a flag."""
import os
import subprocess
import sys
import unittest

import fixture

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CS = os.path.join(SCRIPTS, "cs.py")
OUTSIDE = [".claude/settings.json", ".claude/hooks/cs-guard.sh", "specialists.mk", "Makefile", ".git/hooks/pre-commit"]


class TestInstallOutside(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        fixture.rm(self.root)

    def cs(self, *args):
        p = subprocess.run([sys.executable, CS, "--target", self.root, "harness", "install"] + list(args),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, timeout=120)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def exists(self, rel):
        return os.path.lexists(os.path.join(self.root, rel))

    def test_dry_run_lists_outside_and_writes_nothing(self):
        code, out, err = self.cs("--git-hook", "--dry-run")
        self.assertEqual(code, 0, out + err)
        self.assertIn("outside:", out)
        for rel in OUTSIDE:
            self.assertIn(rel, out)
            self.assertFalse(self.exists(rel), rel)
        self.assertFalse(self.exists(".swarm/harness/engine.py"))

    def test_outside_requires_allow_outside(self):
        code, out, err = self.cs("--git-hook")
        self.assertEqual(code, 3, out + err)
        self.assertIn("--allow-outside", err)
        self.assertIn(".claude/settings.json", err)
        for rel in OUTSIDE + [".swarm/harness/engine.py"]:
            self.assertFalse(self.exists(rel), "escreveu %s sem --allow-outside" % rel)
        code, out, err = self.cs("--git-hook", "--allow-outside")
        self.assertEqual(code, 0, out + err)
        for rel in OUTSIDE:
            self.assertTrue(self.exists(rel), rel)
        # reinstalar sem mudança fora de .swarm/ não pede a flag (idempotente)
        code, out, err = self.cs("--git-hook")
        self.assertEqual(code, 0, out + err)
        code, out, err = self.cs("--git-hook", "--dry-run")
        self.assertIn("outside: nenhuma escrita fora de .swarm/", out)

    def test_only_specialists_needs_no_flag(self):
        code, out, err = self.cs("--no-settings", "--no-makefile")
        self.assertEqual(code, 3, out + err)  # o hook cs-guard.sh mora em .claude/hooks/
        self.assertIn(".claude/hooks/cs-guard.sh", err)


if __name__ == "__main__":
    unittest.main()
