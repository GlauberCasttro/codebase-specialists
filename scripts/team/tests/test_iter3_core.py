"""Iteração 3 — `team core from-panel` (1.5+2.4): classificador único, dedup, sem arquivo:linha, ≤40/S0,
recusa por linha com motivo e registro de promoção (check de rt.3)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
from test_roster_core import cs  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402


def set_s0(root, by_agent):
    t = read_json(sp_path(root, "team.json5"))
    for a in t["agents"]:
        if a["name"] in by_agent:
            a["camadas"] = {"s0_core": by_agent[a["name"]]}
    write_json(root, sp_path(root, "team.json5"), t)


class CoreFromPanel(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def core(self):
        return read_json(sp_path(self.root, "team.json5"))["core"]["lines"]

    def test_prose_operator_and_symbol_do_not_sink_everything(self):
        # iteração 2 (py-billing): `//`, `Money.percent` e `pyproject/uv.lock` derrubavam o comando inteiro
        write_json(self.root, sp_path(self.root, "panel", "core-candidates.json5"), {"schema_version": 1, "candidates": [
            {"facts": ["rules.lint.ruff-e"], "regras": ["Nunca use `//` com dinheiro; ruff seleciona E em src"],
             "reviewers": ["a", "b"], "agents": ["dev-billing"]},
            {"facts": ["rat.adr.money"], "regras": ["Arredonde com `Money.percentual` antes de somar"],
             "reviewers": ["a", "b"], "agents": ["dev-billing"]},
            {"facts": ["br.refund.window"], "regras": ["Reembolso só até 30 dias (src/billing/refund.py:4)"],
             "reviewers": ["a", "b"], "agents": ["dev-billing"]}]})
        code, o, e = cs(self.root, "team", "core", "from-panel")
        self.assertEqual(code, 0, e + o)
        texts = [l["text"] for l in self.core()]
        self.assertIn("Nunca use `//` com dinheiro; ruff seleciona E em src", texts)
        self.assertIn("Reembolso só até 30 dias (src/billing/refund.py)", texts)  # sem :linha
        rec = read_json(sp_path(self.root, "panel", "core-promotion.json5"))
        self.assertEqual(len(rec["promoted"]), 2)
        self.assertEqual(len(rec["refused"]), 1)
        self.assertIn("Money.percentual", rec["refused"][0]["why"])
        self.assertIn("recusada", o)

    def test_dedup_near_duplicates(self):
        # iteração 2 (go-polyglot): 26 linhas com ~8 quase-duplicadas
        set_s0(self.root, {
            "dev-billing": [{"text": "Dinheiro em centavos inteiros, nunca float", "facts": ["rat.adr.money"]}],
            "dev-orders": [{"text": "Dinheiro sempre em centavos inteiros, nunca float.",
                            "facts": ["rat.adr.money", "rules.neg.no-float-money"]}],
            "dev-catalog": [{"text": "Valores monetários: centavos inteiros, nunca float",
                             "facts": ["rules.neg.no-float-money"]}]})
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        self.assertEqual(len(self.core()), 1, self.core())

    def test_cap_40(self):
        import itertools
        ids = ["rat.adr.money", "gl.invoice", "br.refund.window", "rules.lint.ruff-e", "rules.neg.no-float-money",
               "ops.test.unittest", "ops.lint.ruff", "hist.fix.abc1234", "graph.pagerank", "inv.files"]
        words = ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliett"]
        items = [{"text": "%s%d %s%d" % (words[i], n, words[j], n * 7), "facts": [ids[i], ids[j]]}
                 for n, (i, j) in enumerate(itertools.combinations(range(10), 2))]
        self.assertGreater(len(items), 40)
        set_s0(self.root, {"dev-billing": items})
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        self.assertEqual(len(self.core()), 40)
        rec = read_json(sp_path(self.root, "panel", "core-promotion.json5"))
        self.assertTrue(any("sem espaço" in r["why"] for r in rec["refused"]))

    def test_rt3_check_requires_promotion(self):
        code, o, e = cs(self.root, "panel", "consolidate", "--check", "--core")
        self.assertNotEqual(code, 0)
        set_s0(self.root, {"dev-billing": [{"text": "Dinheiro em centavos inteiros", "facts": ["rat.adr.money"]}]})
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        from team.roster import core_check
        self.assertEqual(core_check(self.root), [])
        # candidatas mudaram depois da promoção → rt.3 de novo
        write_json(self.root, sp_path(self.root, "panel", "core-candidates.json5"), {"schema_version": 1, "candidates": []})
        self.assertTrue(core_check(self.root))


if __name__ == "__main__":
    unittest.main()
