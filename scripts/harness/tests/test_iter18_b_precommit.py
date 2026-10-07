"""iter18 R5 — pre-commit (`guard.py check-diff --staged`): allowed_paths de delegação em voo só entram no commit
depois do accept; a árvore de trabalho (sem --staged) continua livre para o trabalho em voo."""
import os
import subprocess
import unittest

import fixture
import hcore

GUARD = os.path.join(fixture.ENGINE, "guard.py")
REL = "src/billing/discount.py"


def check_diff(root, staged):
    argv = ["python3", GUARD, "check-diff", "--root", root] + (["--staged"] if staged else [])
    e = dict(os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run(argv, cwd=root, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return p.returncode, p.stdout.decode()


class TestPreCommitEsperaAceite(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.dispatched(self.root)
        fixture.write(self.root, REL)

    def tearDown(self):
        fixture.rm(self.root)

    def test_dispatched_staged_barra(self):
        fixture.git(self.root, "add", "--", REL)
        code, out = check_diff(self.root, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: %s " % REL, out)
        self.assertIn("T-1", out)
        self.assertIn("accept", out)

    def test_returned_staged_barra(self):
        fixture.submit_ok(self.root)
        self.assertEqual(hcore.load_board(self.root)["tasks"][0]["delegations"][-1]["state"], "RETURNED")
        fixture.git(self.root, "add", "--", REL)
        code, out = check_diff(self.root, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: %s " % REL, out)

    def test_arvore_de_trabalho_continua_livre_em_voo(self):
        code, out = check_diff(self.root, staged=False)
        self.assertNotIn("FORA: %s " % REL, out)

    def test_fora_do_allowed_continua_barrando(self):
        fixture.write(self.root, "src/users/model.py", "AGE = 21\n")
        fixture.git(self.root, "add", "--", "src/users/model.py")
        code, out = check_diff(self.root, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: src/users/model.py (fora de qualquer allowed_paths em voo)", out)


if __name__ == "__main__":
    unittest.main()
