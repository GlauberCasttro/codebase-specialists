"""`cs.py init` grava a versão da skill (VERSION) e upgrade_history vazio; merge não mascara alvo legado."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SCRIPTS)
CS = os.path.join(SCRIPTS, "cs.py")
SKILL = os.path.dirname(SCRIPTS)

from cslib import json5io  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402


class InitSkillVersion(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cs-ver-")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.env = dict(os.environ)
        for k in ("CLAUDE_PROJECT_DIR", "CS_SKILL_VERSION_FILE", "CS_MIGRATIONS_FILE"):
            self.env.pop(k, None)
        with open(os.path.join(SKILL, "VERSION")) as fh:
            self.version = fh.read().strip()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cs(self, *args):
        return subprocess.run([sys.executable, CS, "--target", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)

    def run_json(self):
        return json5io.load(os.path.join(self.root, STATE_DIR, "run.json5"))

    def test_init_records_version(self):
        self.assertEqual(self.cs("init").returncode, 0)
        run = self.run_json()
        self.assertEqual(run["skill_version"], self.version)
        self.assertEqual(run["upgrade_history"], [])

    def test_merge_keeps_legacy_unversioned(self):
        os.makedirs(os.path.join(self.root, STATE_DIR))
        json5io.dump({"schema_version": 1, "run_id": "x", "target": self.root, "platforms": ["cursor"],
                      "stages": {}}, os.path.join(self.root, STATE_DIR, "run.json5"), "teste")
        self.assertEqual(self.cs("init").returncode, 0)
        self.assertNotIn("skill_version", self.run_json())   # legado continua legado → upgrade cuida

    def test_force_records_version(self):
        self.assertEqual(self.cs("init").returncode, 0)
        self.assertEqual(self.cs("init", "--force").returncode, 0)
        self.assertEqual(self.run_json()["skill_version"], self.version)


if __name__ == "__main__":
    unittest.main()
