"""cs.py emit budget (specialize.4): mede S0/S1/S2/kernel sem escrever nada."""
import contextlib
import io
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
for p in (SCRIPTS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import fixture  # noqa: E402
from emit import cli  # noqa: E402
from test_emit import snapshot  # noqa: E402


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def budget(self):
        return run("budget", "--target", self.root, "--platforms", "claude-code,cursor,copilot,codex")

    def test_ok_and_writes_nothing(self):
        before = snapshot(self.root)
        code, out, err = self.budget()
        self.assertEqual(code, 0, err)
        for layer in ("S0", "S1", "S2", "ORCH"):
            self.assertIn(layer, out)
        self.assertEqual(before, snapshot(self.root))

    def test_s1_over_budget_exit_1(self):
        team = fixture.team()
        team["agents"][1]["card"]["knows"] = [{"text": "fato %d" % i} for i in range(90)]
        fixture.write_team(self.root, team)
        code, _, err = self.budget()
        self.assertEqual(code, 1)
        self.assertIn("S1", err)

    def test_s0_over_budget_exit_1(self):
        team = fixture.team()
        team["core"]["lines"] = [{"text": "linha %d" % i} for i in range(38)]
        fixture.write_team(self.root, team)
        code, _, err = self.budget()
        self.assertEqual(code, 1)
        self.assertIn("S0", err)

    def test_invalid_team_exit_2(self):
        team = fixture.team()
        team["agents"][0]["card"] = None
        fixture.write_team(self.root, team)
        self.assertEqual(self.budget()[0], 2)

    def test_json_output(self):
        code, out, _ = run("budget", "--target", self.root, "--json")
        self.assertEqual(code, 0)
        self.assertIn('"S1"', out)


if __name__ == "__main__":
    unittest.main()
