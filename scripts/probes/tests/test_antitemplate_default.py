"""Regressão iteração 1 (G3 sem fonte de controle): o controle default é evals/reference/generic-cards (*.md)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.antitemplate import DEFAULT_CONTROL, load_control, run_antitemplate  # noqa: E402


class AntitemplateDefault(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        team, _ = derive(self.root)
        for a in team["agents"]:
            a["card"] = {"description": "Use para %s em src/billing." % a["name"],
                         "mission": "Mantém a janela de reembolso de 30 dias em src/billing/refund.py.",
                         "done_when": "`python3 -m unittest discover -s tests` sai 0"}
        write_json(self.root, sp_path(self.root, "team.json5"), team)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_default_control_is_generic_cards(self):
        self.assertTrue(DEFAULT_CONTROL.endswith(os.path.join("evals", "reference", "generic-cards")))
        ctrl = load_control(DEFAULT_CONTROL)
        kinds = {a["name"]: a["kind"] for a in ctrl["agents"]}
        self.assertEqual(kinds["code-reviewer"], "gate")
        self.assertEqual(kinds["backend-developer"], "dev")
        rep = run_antitemplate(self.root, None)
        self.assertEqual(rep["control"], DEFAULT_CONTROL)
        self.assertTrue(rep["pass"], rep)

    def test_generic_card_copied_fails(self):
        team = read_json(sp_path(self.root, "team.json5"))
        with open(os.path.join(DEFAULT_CONTROL, "code-reviewer.md")) as fh:
            body = fh.read().split("---", 2)[2]
        for a in team["agents"]:
            if a["name"] == "reviewer":
                a["card"]["mission"] = body
        write_json(self.root, sp_path(self.root, "team.json5"), team)
        rep = run_antitemplate(self.root, DEFAULT_CONTROL)
        self.assertFalse(rep["agents"]["reviewer"]["pass"])


if __name__ == "__main__":
    unittest.main()
