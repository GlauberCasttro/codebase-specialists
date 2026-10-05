"""Iteração 3 — `cs.py init` faz MERGE idempotente (contrato `init`) e `cs.py stage skip` (contrato `fast`)."""
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


class Base(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-it3-"))
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_PROJECT_DIR", None)
        self.env.pop("CS_STAGES_FILE", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cs(self, *args):
        p = subprocess.run([sys.executable, CS, "--target", self.root] + list(args), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=self.env)
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def run_json(self):
        return json5io.load(os.path.join(self.root, STATE_DIR, "run.json5"))


class InitMerge(Base):
    def test_init_after_stage_load_merges_platforms_and_keeps_progress(self):
        # iteração 2: `stage load init`/`stage check init.1` criava run.json5 e o `init --platforms` posterior
        # dizia "já existia" — plataformas escolhidas no init.2 nunca entravam
        self.assertEqual(self.cs("stage", "load", "init")[0], 0)
        self.assertEqual(self.cs("stage", "check", "init.2", "--answer", "só cursor")[0], 0)
        rid = self.run_json()["run_id"]
        code, out, err = self.cs("init", "--platforms", "cursor")
        self.assertEqual(code, 0, err)
        self.assertIn("mesclado", out)
        run = self.run_json()
        self.assertEqual(run["platforms"], ["cursor"])
        self.assertEqual(run["run_id"], rid)
        self.assertEqual(run["stages"]["init"]["substages"]["init.2"]["status"], "done")
        # idempotente
        code, out, _ = self.cs("init", "--platforms", "cursor")
        self.assertIn("nada mudou", out)

    def test_init_check_requires_explicit_init(self):
        self.cs("stage", "load", "init")
        self.assertEqual(self.cs("init", "--check")[0], 1)
        self.cs("init")
        self.assertEqual(self.cs("init", "--check")[0], 0)

    def test_merge_reaches_team_json5(self):
        self.cs("init")
        sp = os.path.join(self.root, STATE_DIR)
        json5io.dump({"schema_version": 1, "platforms": ["claude-code", "codex", "copilot", "cursor"], "agents": []},
                     os.path.join(sp, "team.json5"), "t", target=self.root)
        self.assertEqual(self.cs("init", "--platforms", "claude-code,copilot")[0], 0)
        self.assertEqual(json5io.load(os.path.join(sp, "team.json5"))["platforms"], ["claude-code", "copilot"])

    def test_check_repo_refuses_subdirectory(self):
        sub = os.path.join(self.root, "pkg")
        os.makedirs(sub)
        p = subprocess.run([sys.executable, CS, "--target", sub, "init", "--check-repo"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=self.env)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(self.cs("init", "--check-repo")[0], 0)


class StageSkip(Base):
    def test_skip_needs_reason_and_skippable(self):
        self.cs("init")
        self.assertEqual(self.cs("stage", "skip", "rt.1", "--reason", "")[0], 2)
        code, _, err = self.cs("stage", "skip", "init.3", "--reason", "x")
        self.assertEqual(code, 2)
        self.assertIn("não pode ser pulada", err)

    def test_skip_shows_in_status_and_needs_previous_stage(self):
        self.cs("init")
        code, _, err = self.cs("stage", "skip", "rt.1", "--reason", "--fast pedido pelo usuário")
        self.assertEqual(code, 2)  # specialize não fechou
        run = self.run_json()
        for st in ("init", "scan", "specialize"):
            run.setdefault("stages", {})[st] = {"status": "done", "substages": {}}
        json5io.dump(run, os.path.join(self.root, STATE_DIR, "run.json5"), "x", target=self.root)
        for sid in ("rt.1", "rt.2", "rt.3", "rt.4"):
            code, out, err = self.cs("stage", "skip", sid, "--reason", "--fast pedido pelo usuário")
            self.assertEqual(code, 0, err)
        code, out, _ = self.cs("stage", "status")
        st = json5io.loads(out)
        self.assertEqual([s["id"] for s in st["skipped"]], ["rt.1", "rt.2", "rt.3", "rt.4"])
        self.assertEqual(st["skipped"][0]["reason"], "--fast pedido pelo usuário")
        os.makedirs(os.path.join(self.root, STATE_DIR, "stages"), exist_ok=True)
        json5io.dump({"schema_version": 1, "stage": "specialize", "pending": []},
                     os.path.join(self.root, STATE_DIR, "stages", "specialize.handoff.json5"), "h",
                     target=self.root)
        code, out, err = self.cs("stage", "done", "round-table-deep-specialize")
        self.assertEqual(code, 0, err)
        ho = json5io.load(os.path.join(self.root, STATE_DIR, "stages",
                                       "round-table-deep-specialize.handoff.json5"))
        self.assertEqual(len(ho["skipped"]), 4)


if __name__ == "__main__":
    unittest.main()
