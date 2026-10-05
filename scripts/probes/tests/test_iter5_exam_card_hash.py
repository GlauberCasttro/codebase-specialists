"""Iteração 5 (P0): o verify aceitou G4 com cartões consertados DEPOIS do exame. O ciclo de exame guarda o hash
do cartão examinado; cartão mudou ⇒ G4 daquele agente PENDENTE (reexame) — repontuar as MESMAS respostas não
lava o hash; respostas novas (reexame) religam ao cartão atual."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_final as TF  # noqa: E402
from test_final import cs  # noqa: E402
from test_roster_core import card  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402


class ExamBoundToCard(unittest.TestCase):
    setUp = TF.FinalTest.setUp
    tearDown = TF.FinalTest.tearDown
    exams = TF.FinalTest.exams

    def put_card(self, name, mission):
        c = card(name)
        c["mission"] = mission
        full = os.path.join(self.root, ".swarm", "tmp", "%s.json5" % name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(c))
        code, o, e = cs(self.root, "team", "card", "set", name, "--file", full, "--force")
        self.assertEqual(code, 0, o + e)

    def test_card_changed_after_exam_is_pending(self):
        agents = self.exams("h1")
        self.assertIn("dev-billing", agents)
        self.put_card("dev-billing", "Mantém billing correto.")
        code, o, e = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 0, o + e)
        cyc = read_json(sp_path(self.root, "probes", "cycles.json5"))["dev-billing"][-1]
        self.assertTrue(cyc.get("card_sha256"))
        # conserto do cartão DEPOIS do exame
        self.put_card("dev-billing", "Mantém billing correto (conserto de existência).")
        code, o, e = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 1, o + e)
        self.assertIn("PENDENTE", o + e)
        # repontuar as mesmas respostas não lava (segundo verify)
        code, o, e = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 1, o + e)
        rep = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(rep["agents"]["dev-billing"]["status"], "pendente-reexame")
        self.assertEqual(rep["final"]["pending_reexam"], ["dev-billing"])
        from probes.final import pending_reexam
        self.assertEqual([a for a, _ in pending_reexam(self.root)], ["dev-billing"])
        # validate.3 também acusa
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--examined")[0], 1)
        # reexame: respostas NOVAS sobre o cartão atual
        ap = sp_path(self.root, "probes", "exams", "dev-billing.answers.json5")
        ans = read_json(ap)
        write_json(self.root, ap, list(reversed(ans)))
        code, o, e = cs(self.root, "probes", "check", "dev-billing")
        self.assertEqual(code, 0, o + e)
        code, o, e = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 0, o + e)
        self.assertEqual(pending_reexam(self.root), [])

    def test_legacy_cycle_without_hash_uses_card_records(self):
        self.exams("h2")
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final")[0], 0)
        p = sp_path(self.root, "probes", "cycles.json5")
        cyc = read_json(p)
        for lst in cyc.values():
            for c in lst:
                c.pop("card_sha256", None)
                c.pop("examined_at", None)
                c["at"] = "2000-01-01T00:00:00Z"
        write_json(self.root, p, cyc)
        self.put_card("dev-billing", "cartão registrado depois do exame")
        from probes.final import pending_reexam
        self.assertEqual([a for a, _ in pending_reexam(self.root)], ["dev-billing"])


if __name__ == "__main__":
    unittest.main()
