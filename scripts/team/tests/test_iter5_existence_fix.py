"""Iteração 5 (ts-shop --fast, P0): sem mesa redonda não existe painel consolidado, e `team card revise --file`
(o caminho do conserto de existência) recusava ("painel não consolidado") — o executor gravou por fora com
`card set`. O conserto de existência devolvido ao autor tem de ser aceito SEM painel; a revisão do autor (rt.4)
continua exigindo painel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
from test_roster_core import card, cs  # noqa: E402

from team._shared_tmp.common import read_json, sp_path  # noqa: E402
from team.derive import derive  # noqa: E402


class FixWithoutPanel(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        bad = card("dev-billing")
        bad["anchors"] = ["src/billing/invoice.py", "src/billing/nao_existe.py"]
        self.put(".swarm/tmp/bad.json5", bad)
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/bad.json5")[0], 0)
        self.assertFalse(os.path.exists(sp_path(self.root, "panel", "dev-billing.json5")))

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        import json
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(obj))
        return rel

    def test_existence_fix_accepted_without_panel(self):
        self.put(".swarm/tmp/fix.json5", card("dev-billing"))
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/fix.json5",
                        "--note", "conserto de existência")
        self.assertEqual(code, 0, o + e)
        st = read_json(sp_path(self.root, "cards", "status.json5"))["dev-billing"]
        self.assertEqual(len(st["existence_fixes"]), 1)
        self.assertTrue(st["existence_fixes"][0]["existence_fix"])
        self.assertNotIn("revised", st)  # não conta como revisão do autor (rt.4)
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertEqual(row["problems_drafted"], [], row)  # não é "alterado fora de card set|revise"
        # sem falta de existência no cartão atual, sem painel não há o que consertar
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/fix.json5",
                            "--note", "outra")[0], 2)

    def test_fix_without_panel_still_checks_new_card(self):
        worse = card("dev-billing")
        worse["anchors"] = ["src/billing/outro_inexistente.py"]
        self.put(".swarm/tmp/worse.json5", worse)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/worse.json5",
                        "--note", "x")
        self.assertEqual(code, 2, o + e)
        self.assertIn("outro_inexistente.py", e)

    def test_revision_without_change_still_needs_panel(self):
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--note", "rt.4")
        self.assertEqual(code, 2, o + e)
        self.assertIn("não consolidado", e)


if __name__ == "__main__":
    unittest.main()
