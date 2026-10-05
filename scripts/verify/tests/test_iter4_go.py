"""Iteração 4 — decisoes.regra_go: GO exige TODOS os agentes `especialista` e todos os gates verdes; qualquer
`nao-especialista` (aceito ou não) ⇒ NO-GO, sempre (go-polyglot da rodada 3 saiu GO com ops aceito).
Relatório diz qual modo rodou (--fast padrão × --full) e mostra `baseline_saturated`."""
import os
import unittest

from helpers import synth

from cslib import json5io
from cslib.paths import STATE_DIR
from verify import gates as G
from verify import report


def allpass(t, c):
    return [G.gate(g, n, True, "ok", "x") for g, n in G.GATES]


class RegraGo(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def probes_report(self, agents, allowed=None):
        doc = {"schema_version": 1, "g4": "PASS", "agents": agents,
               "final": {"non_specialist": sorted(a for a, r in agents.items() if r.get("status") == "nao-especialista"),
                         "allowed": allowed}}
        json5io.dump(doc, os.path.join(self.root, STATE_DIR, "probes", "report.json5"), "teste", target=self.root)

    def run_json(self, skipped):
        subs = {"validate.4": {"status": "skipped", "reason": "--fast", "at": "x"}} if skipped else {}
        json5io.dump({"schema_version": 1, "stages": {"validate": {"status": "in_progress", "substages": subs}}},
                     os.path.join(self.root, STATE_DIR, "run.json5"), "teste", target=self.root)

    def test_accepted_non_specialist_is_no_go(self):
        self.probes_report({"dev-a": {"decision": "PASS", "status": "especialista"},
                            "ops": {"decision": "FAIL", "status": "nao-especialista"}},
                           allowed={"agents": ["ops"], "reason": "sem sonda discriminante"})
        doc = G.verify(self.root, gates_fn=allpass)
        self.assertEqual(doc["decision"], "NO-GO")
        self.assertEqual(doc["non_specialist"], ["ops"])
        g4 = [g for g in doc["gates"] if g["id"] == "G4"][0]
        self.assertFalse(g4["passed"])
        self.assertIn("nao-especialista", g4["evidence"])

    def test_em_refino_is_no_go_and_all_specialists_is_go(self):
        self.probes_report({"dev-a": {"decision": "PASS", "status": "especialista"},
                            "ops": {"decision": "FAIL", "status": "em-refino"}})
        self.assertEqual(G.verify(self.root, gates_fn=allpass)["decision"], "NO-GO")
        self.probes_report({"dev-a": {"decision": "PASS", "status": "especialista"},
                            "ops": {"decision": "PASS", "status": "especialista"}})
        self.assertEqual(G.verify(self.root, gates_fn=allpass)["decision"], "GO")

    def test_report_says_mode_and_saturation(self):
        self.probes_report({"ops": {"decision": "PASS", "status": "especialista", "score_territory": 1.0,
                                    "baseline_saturated": True}})
        self.run_json(skipped=True)
        text = report.build(self.root)
        self.assertIn("Modo: --fast", text)
        self.assertIn("baseline_saturated", text)
        self.run_json(skipped=False)
        self.assertIn("Modo: --full", report.build(self.root))


if __name__ == "__main__":
    unittest.main()
