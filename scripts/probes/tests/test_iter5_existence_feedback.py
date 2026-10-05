"""Iteração 5 (P0): o check de existência roda em TODOS os modos e o resultado volta ao AUTOR: `probes existence`
grava um pacote por cartão com falta em .swarm/probes/existence-fix/<agente>.json5 (com o comando de
conserto) e apaga o pacote quando o cartão fica limpo."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402
from test_roster_core import card, cs  # noqa: E402

from team._shared_tmp.common import read_json, sp_path  # noqa: E402
from team.derive import derive  # noqa: E402


class Feedback(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(obj))
        return rel

    def test_feedback_pack_per_author(self):
        bad = card("dev-billing")
        bad["anchors"] = ["src/billing/nao_existe.py"]
        self.put(".swarm/tmp/bad.json5", bad)
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/bad.json5")[0], 0)
        code, o, e = cs(self.root, "probes", "existence")
        self.assertEqual(code, 1, o + e)
        fb = sp_path(self.root, "probes", "existence-fix", "dev-billing.json5")
        self.assertTrue(os.path.isfile(fb), o + e)
        doc = read_json(fb)
        self.assertEqual(doc["missing"][0]["value"], "src/billing/nao_existe.py")
        self.assertIn("team card revise dev-billing --file", doc["fix"])
        rep = read_json(sp_path(self.root, "probes", "existence.json5"))
        self.assertIn("dev-billing", rep["feedback"])
        # conserto pelo caminho devolvido (sem painel — caminho --fast) → pacote some
        self.put(".swarm/tmp/fix.json5", card("dev-billing"))
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/fix.json5",
                        "--note", "conserto de existência")
        self.assertEqual(code, 0, o + e)
        cs(self.root, "probes", "existence")
        self.assertFalse(os.path.exists(fb))


if __name__ == "__main__":
    unittest.main()
