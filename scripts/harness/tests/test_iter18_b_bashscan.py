"""iter18 R6 — bashscan: git somente leitura (check-ignore, ls-remote, count-objects) e escrita continua fora."""
import unittest

import fixture  # noqa: F401  (sys.path do motor)
import bashscan

from test_guards import GuardBase, B, hook


class TestGitSomenteLeitura(unittest.TestCase):
    def test_novos_subcomandos_de_leitura(self):
        for sub in ("check-ignore", "ls-remote", "count-objects"):
            self.assertEqual(bashscan.git_effect(sub), "read", sub)

    def test_escrita_continua_tree(self):
        for sub in ("checkout", "reset", "clean", "gc", "stash", "restore", "switch"):
            self.assertEqual(bashscan.git_effect(sub), "tree", sub)


class TestGuardLiberaLeituraGit(GuardBase):
    def test_orquestrador_roda_leitura_git(self):
        for cmd in ("git check-ignore -v src/billing/obj/x.dll", "git ls-remote origin", "git count-objects -v"):
            code, out, err = hook(self.root, "pre-bash", B(self.root, cmd))
            self.assertEqual(code, 0, "%s bloqueado:\n%s%s" % (cmd, out, err))


if __name__ == "__main__":
    unittest.main()
