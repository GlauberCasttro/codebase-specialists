"""Regressões iteração 1 (G4 oficial 1/9; 7/9 com gabarito certo): gerador E checker de sondas.
Um caso de cada: Makefile:N; termo → definição certa; sonda de regra mecânica; regra de negócio por fato."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import Checker, cites  # noqa: E402
from probes.generate import generate  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo(extra_files={"src/orders/orders_repo.py": "class Orders:\n    pass\n"})
        fd = os.path.join(self.root, ".swarm", "facts")
        g = read_json(os.path.join(fd, "graph.json5"))
        g["symbols"].append({"name": "Orders", "kind": "class", "path": "src/orders/orders_repo.py", "line": 1})
        write_json(self.root, os.path.join(fd, "graph.json5"), g)
        gl = read_json(os.path.join(fd, "glossary.json5"))
        # glossário do scan aponta o termo `Orders` para a linha de `class Order` (struct errado)
        gl["facts"].append(synth.fact("gl.orders", "glossary", "Orders é canônico", [{"file": "src/orders/order.py",
                                                                                      "line": 1}],
                                      ["src/orders/**"], {"canonical": "Orders", "category": "business"}))
        write_json(self.root, os.path.join(fd, "glossary.json5"), gl)
        r = read_json(os.path.join(fd, "rules.json5"))
        r["facts"].append(synth.fact("rules.tests.billing", "rules", "1 arquivo de teste, 5 casos",
                                     [{"file": "tests/test_billing.py", "line": 1}], ["src/billing/**"],
                                     {"kind": "test_asserts", "count": 5}))
        r["facts"].append(synth.fact("rules.cfg.make.test", "rules", "make test roda a suíte",
                                     [{"file": "Makefile", "line": 1}], ["src/**"], {"kind": "ci", "tool": "make"}))
        write_json(self.root, os.path.join(fd, "rules.json5"), r)
        br = read_json(os.path.join(fd, "business_rules.json5"))
        br["facts"].append(synth.fact("br.orders.assign", "business_rules", "assign only from created",
                                      [{"file": "src/orders/order.py", "line": 1}], ["src/orders/**"],
                                      {"subject": "atribuição de pedido", "kind": "state",
                                       "value": "assign only from created"}))
        write_json(self.root, os.path.join(fd, "business_rules.json5"), br)
        idx = read_json(os.path.join(fd, "index.json5"))
        idx["facts"] += ["gl.orders", "rules.tests.billing", "rules.cfg.make.test", "br.orders.assign"]
        write_json(self.root, os.path.join(fd, "index.json5"), idx)
        derive(self.root, force=True)
        self.bank = generate(self.root)
        self.ch = Checker(self.root)

    def tearDown(self):
        synth.cleanup(self.root)


class TestCheckerAndGenerator(Base):
    def test_makefile_line_is_a_citation(self):
        self.assertEqual(cites("imposto em Makefile:1"), [("Makefile", 1)])
        self.assertEqual(cites("ver Dockerfile:1 e src/x.py:2"), [("Dockerfile", 1), ("src/x.py", 2)])
        probe = {"type": "prohibition", "answer": {"exists": True, "enforced_at": [{"file": "Makefile", "line": 1}]}}
        ok, hall, why, _ = self.ch.score_one(probe, {"answer": "Makefile:1", "evidence": ["Makefile:1"]})
        self.assertTrue(ok, why)
        # evidência com comentário depois do arquivo:linha não é alucinação
        ok, hall, why, _ = self.ch.score_one(probe, {"answer": "Makefile:1",
                                                     "evidence": ["Makefile:1 (alvo test)"]})
        self.assertTrue(ok, why)
        self.assertFalse(hall)

    def test_term_where_points_to_real_definition(self):
        ps = [p for p in self.bank["probes"] if p["type"] == "term" and p["answer"].get("term") == "Orders"
              and p["answer"].get("variant") == "where"]
        for p in ps:
            self.assertEqual((p["answer"]["path"], p["answer"]["line"]), ("src/orders/orders_repo.py", 1))
        probe = {"type": "term", "answer": {"exists": True, "variant": "where", "term": "Orders",
                                            "path": "src/orders/order.py", "line": 1}}
        ok, _, why, _ = self.ch.score_one(probe, {"answer": "src/orders/orders_repo.py:1",
                                                  "evidence": ["src/orders/orders_repo.py:1"]})
        self.assertTrue(ok, why)  # gabarito antigo errado: a definição exata do termo também vale

    def test_no_mechanical_rule_probe_from_test_summary(self):
        bad = [p for p in self.bank["probes"] if p["type"] == "prohibition"
               and "rules.tests.billing" in p.get("atomic_facts", [])]
        self.assertEqual(bad, [])
        self.assertFalse(any(p["type"] == "prohibition" and
                             any(e["file"].startswith("tests/") and e["line"] == 1 for e in p["answer"]["enforced_at"])
                             for p in self.bank["probes"]))

    def test_business_rule_by_fact_not_literal(self):
        probe = {"type": "business_rule", "answer": {"exists": True, "value": "assign only from created",
                                                     "sources": [{"file": "src/orders/order.py", "line": 1}]}}
        ans = {"answer": "só pode atribuir pedido no estado created (src/orders/order.py:1)",
               "evidence": ["src/orders/order.py:1"]}
        ok, _, why, _ = self.ch.score_one(probe, ans)
        self.assertTrue(ok, why)
        num = {"type": "business_rule", "answer": {"exists": True, "value": "30",
                                                   "sources": [{"file": "src/billing/refund.py", "line": 4}]}}
        self.assertTrue(self.ch.score_one(num, {"answer": "30 dias em src/billing/refund.py:4",
                                                "evidence": ["src/billing/refund.py:4"]})[0])
        self.assertFalse(self.ch.score_one(num, {"answer": "15 dias em src/billing/refund.py:4",
                                                 "evidence": ["src/billing/refund.py:4"]})[0])


if __name__ == "__main__":
    unittest.main()
