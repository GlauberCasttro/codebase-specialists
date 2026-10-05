"""check `cs-session save --check` (approve.3) resolve para o motor da skill, não para um script inexistente."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SCRIPTS)

from stage import engine  # noqa: E402


class HarnessBinChecks(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cs-stage-bin-")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_session_check_runs_skill_engine(self):
        argv = engine.check_argv("cs-session save --check", self.root)
        self.assertEqual(argv[1], os.path.join(SCRIPTS, "harness", "engine", "session.py"))
        self.assertEqual(argv[2:4], ["--root", self.root])
        ok, code, detail, _ = engine.run_check(self.root, "cs-session save --check")
        self.assertFalse(ok)
        self.assertEqual(code, 1, detail)  # executou e reprovou (sem save); 127 seria "indisponível"

    def test_all_bins_resolve(self):
        for b in ("cs-state", "cs-session", "cs-route", "cs-mem"):
            self.assertTrue(os.path.isfile(engine.check_argv(b + " x", self.root)[1]), b)


if __name__ == "__main__":
    unittest.main()
