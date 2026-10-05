"""Iteração 5 (P0): verify NÃO passa quando o cartão mudou depois do exame aprovado — G4 PENDENTE (reexame)."""
import os
import unittest

from helpers import synth

from cslib import json5io
from cslib.paths import STATE_DIR
from team.cards import _sha
from verify import gates as G


def allpass(t, c):
    return [G.gate(g, n, True, "ok", "x") for g, n in G.GATES]


CARD = {"description": "d", "mission": "m", "done_when": "x"}


class StaleExam(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.dump(("team.json5",), {"agents": [{"name": "dev-a", "card": CARD}]})
        self.dump(("probes", "report.json5"), {"schema_version": 1, "agents": {
            "dev-a": {"decision": "PASS", "status": "especialista"}}})

    def tearDown(self):
        synth.cleanup(self.root)

    def dump(self, parts, doc):
        json5io.dump(doc, os.path.join(self.root, STATE_DIR, *parts), "teste", target=self.root)

    def cycles(self, sha):
        self.dump(("probes", "cycles.json5"), {"dev-a": [{"at": "x", "probes_sha256": "p", "answers_sha256": "a",
                                                          "card_sha256": sha, "decision": "PASS", "retakes": 0}]})

    def test_card_changed_after_exam_is_no_go(self):
        self.cycles(_sha(dict(CARD, mission="antes do conserto")))
        doc = G.verify(self.root, gates_fn=allpass)
        self.assertEqual(doc["decision"], "NO-GO")
        self.assertEqual(doc["pending_reexam"], ["dev-a"])
        g4 = [g for g in doc["gates"] if g["id"] == "G4"][0]
        self.assertFalse(g4["passed"])
        self.assertIn("PENDENTE", g4["evidence"])

    def test_same_card_is_go(self):
        self.cycles(_sha(CARD))
        self.assertEqual(G.verify(self.root, gates_fn=allpass)["decision"], "GO")


if __name__ == "__main__":
    unittest.main()
