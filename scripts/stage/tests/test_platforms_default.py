"""Regressão iteração 1: init/stage load init gravavam platforms: [] (default das 4 nunca aplicado)."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SCRIPTS)
CS = os.path.join(SCRIPTS, "cs.py")

from cslib import json5io  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402

FOUR = ["claude-code", "codex", "copilot", "cursor"]


class PlatformsDefault(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cs-plat-")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cs(self, *args):
        return subprocess.run([sys.executable, CS, "--target", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)

    def plats(self):
        return sorted(json5io.load(os.path.join(self.root, STATE_DIR, "run.json5"))["platforms"])

    def test_init_without_flag_uses_four(self):
        self.assertEqual(self.cs("init").returncode, 0)
        self.assertEqual(self.plats(), FOUR)

    def test_stage_load_init_uses_four(self):
        self.assertEqual(self.cs("stage", "load", "init").returncode, 0)
        self.assertEqual(self.plats(), FOUR)

    def test_existing_empty_list_gets_default(self):
        os.makedirs(os.path.join(self.root, STATE_DIR))
        json5io.dump({"schema_version": 1, "run_id": "x", "target": self.root, "platforms": [], "stages": {}},
                     os.path.join(self.root, STATE_DIR, "run.json5"), "teste")
        self.assertEqual(self.cs("init").returncode, 0)
        self.assertEqual(self.plats(), FOUR)

    def test_explicit_subset_respected(self):
        self.assertEqual(self.cs("init", "--platforms", "cursor").returncode, 0)
        self.assertEqual(self.plats(), ["cursor"])
        r = self.cs("init", "--platforms", "nada")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
