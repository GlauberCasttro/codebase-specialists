"""G16 etapas: load ≤2k tokens por etapa; done com check falhando não avança; retomada na sub-etapa certa."""

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
from stage import engine  # noqa: E402

STAGES = """// stages de teste
{
  schema_version: 1,
  order: ["init", "scan", "last"],
  stages: {
    init: {goal: "g0", substages: [
      {id: "init.1", do: "repo git", ctx: "main", check: "git -C {target} rev-parse --git-dir"},
      {id: "init.2", do: "plataformas", ctx: "user"},
      {id: "init.3", do: "run.json5", ctx: "main", check: "cs.py init --check"},
    ]},
    scan: {goal: "g1", substages: [
      {id: "scan.1", do: "marcador A", ctx: "main", check: "test -f {target}/A"},
      {id: "scan.2", do: "marcador B", ctx: "main", check: "test -f {target}/B"},
      {id: "scan.3", do: "nota", ctx: "main"},
    ]},
    last: {goal: "g2", substages: [{id: "last.1", do: "x", ctx: "main", check: "true"}]},
  },
  limits: {handoff_max_tokens: 2000},
}
"""


class StageG16(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cs-stage-")
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        self.sfdir = tempfile.mkdtemp(prefix="cs-stages-")
        self.sf = os.path.join(self.sfdir, "stages.json5")
        with open(self.sf, "w") as fh:
            fh.write(STAGES)
        self.env = dict(os.environ, CS_STAGES_FILE=self.sf)
        self.env.pop("CLAUDE_PROJECT_DIR", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.sfdir, ignore_errors=True)

    def cs(self, *args):
        return subprocess.run([sys.executable, CS, "--target", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)

    def run_json(self):
        return json5io.load(os.path.join(self.root, STATE_DIR, "run.json5"))

    def close_init(self):
        self.assertEqual(self.cs("stage", "load", "init").returncode, 0)
        self.assertEqual(self.cs("stage", "check", "init.2", "--answer", "claude-code").returncode, 0)
        self.assertEqual(self.cs("init", "--platforms", "claude-code").returncode, 0)  # merge explícito
        r = self.cs("stage", "done", "init")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_load_refuses_when_previous_not_done(self):
        self.cs("stage", "load", "init")
        r = self.cs("stage", "load", "scan")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("não fechou", r.stderr.decode())

    def test_done_with_failing_check_does_not_advance(self):
        self.close_init()
        self.cs("stage", "load", "scan")
        open(os.path.join(self.root, "A"), "w").close()
        self.cs("stage", "check", "scan.3", "--note", "feito")
        r = self.cs("stage", "done", "scan")
        self.assertEqual(r.returncode, 1)
        self.assertIn("scan.2", r.stderr.decode())
        run = self.run_json()
        self.assertEqual(run["current_stage"], "scan")
        self.assertNotEqual(run["stages"]["scan"]["status"], "done")
        self.assertFalse(os.path.exists(os.path.join(self.root, ".swarm/stages/scan.handoff.json5")))
        self.assertNotEqual(self.cs("stage", "load", "last").returncode, 0)

    def test_resume_at_right_substage(self):
        self.close_init()
        open(os.path.join(self.root, "A"), "w").close()
        self.cs("stage", "load", "scan")
        self.assertEqual(self.cs("stage", "check", "scan.1").returncode, 0)
        # "interrupção": nova janela só tem o disco
        out = self.cs("stage", "load", "scan").stdout.decode()
        pkg = json5io.loads(out)
        self.assertEqual(pkg["resume_at"], "scan.2")
        self.assertEqual(pkg["done"], ["scan.1"])
        self.assertIn("handoff_from_init", pkg)
        self.assertEqual(self.cs("stage", "check", "scan.2").returncode, 1)  # B ainda não existe
        pkg = json5io.loads(self.cs("stage", "load", "scan").stdout.decode())
        self.assertEqual(pkg["resume_at"], "scan.2")
        open(os.path.join(self.root, "B"), "w").close()
        self.cs("stage", "check", "scan.3", "--note", "ok")
        self.assertEqual(self.cs("stage", "done", "scan").returncode, 0)
        self.assertEqual(self.run_json()["current_stage"], "last")

    def test_real_stages_load_fit_2k_tokens(self):
        cfg = engine.load_stages(engine.STAGES_FILE)
        run = {"stages": {}}
        for name in cfg["order"]:
            run["stages"][name] = {"status": "done", "substages": {}}
        os.makedirs(os.path.join(self.root, STATE_DIR, "stages"))
        big = {"schema_version": 1, "stage": "x", "produced": ["p/%04d.json5" % i for i in range(3000)],
               "numbers": {}, "pending": ["pendência longa %d" % i for i in range(500)]}
        for name in cfg["order"]:
            json5io.dump(big, engine.handoff_path(self.root, name), "h")
        for name in cfg["order"]:
            run["stages"][name]["status"] = "in_progress"
            pkg, text = engine.load_package(self.root, cfg, run, name)
            self.assertLessEqual(engine.est_tokens(text), 2000, name)
            run["stages"][name]["status"] = "done"

    def test_user_item_requires_answer(self):
        self.cs("stage", "load", "init")
        r = self.cs("stage", "check", "init.2")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--answer", r.stderr.decode())

    def test_missing_check_command_fails_closed(self):
        ok, code, detail, _ = engine.run_check(self.root, "cs-nao-existe --check")
        self.assertFalse(ok)
        self.assertEqual(code, 127)


if __name__ == "__main__":
    unittest.main()
