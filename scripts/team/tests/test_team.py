import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402  (ajusta sys.path para scripts/)

from team._shared_tmp import json5mini  # noqa: E402
from team._shared_tmp.common import CsError, read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from team.maps import build_maps  # noqa: E402
from team.validate import validate  # noqa: E402


def by_name(team):
    return {a["name"]: a for a in team["agents"]}


class DeriveTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.team, self.deriv = derive(self.root)
        self.a = by_name(self.team)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_bounded_contexts_and_frontend(self):
        devs = sorted(n for n, a in self.a.items() if n.startswith(("dev-", "frontend")))
        self.assertEqual(devs, ["dev-billing", "dev-catalog", "dev-orders", "dev-shared", "frontend"])
        self.assertEqual(self.a["dev-billing"]["territory"], ["src/billing/**"])
        self.assertIn("web/**", self.a["frontend"]["territory"])
        for a in self.team["agents"]:
            self.assertIsNone(a["card"])

    def test_shared_kernel_becomes_reads_of_all_devs(self):
        # regressão iteração 1: utils compartilhado virava território de escrita do architect
        self.assertIn("dev-shared", self.a)
        self.assertEqual(self.a["dev-shared"]["kind"], "dev")
        self.assertEqual(self.a["dev-shared"]["territory"], ["src/shared/**"])
        self.assertNotIn("src/shared/**", self.a["architect"]["territory"])
        for n in ("dev-billing", "dev-catalog", "dev-orders", "frontend"):
            self.assertIn("src/shared/**", self.a[n]["reads"], n)
        self.assertTrue(any(d["step"] == "kernel" for d in self.deriv["decisions"]))

    def test_tiny_unit_is_merged_into_most_coupled(self):
        self.assertIn("src/tiny/**", self.a["dev-catalog"]["territory"])

    def test_transversal_and_conditional_roles(self):
        for n, kind in (("reviewer", "gate"), ("security", "gate"), ("qa", "dev"), ("architect", "design"),
                        ("po", "product"), ("ops", "ops"), ("dba", "dev")):
            self.assertEqual(self.a[n]["kind"], kind, n)
        for g in ("reviewer", "security"):
            self.assertFalse({"Edit", "Write"} & set(self.a[g]["tools"]))
            self.assertEqual(self.a[g]["territory"], [])
        self.assertEqual(self.a["qa"]["territory"], ["tests/**"])
        self.assertEqual(self.a["dba"]["territory"], ["db/**"])
        self.assertIn(".github/**", self.a["ops"]["territory"])

    def test_invariants_terms_and_business_rules_reach_territory_and_gates(self):
        inv = self.a["dev-billing"]["invariants"]
        self.assertIn("rules.neg.no-float-money", inv)
        self.assertIn("br.refund.window", inv)
        self.assertIn("gl.invoice", self.a["dev-billing"]["facts_used"])
        self.assertNotIn("br.refund.window", self.a["dev-catalog"]["invariants"])
        self.assertIn("br.refund.window", self.a["reviewer"]["invariants"])
        self.assertIn("rules.lint.ruff-e", self.a["reviewer"]["invariants"])
        # regressão iteração 1: gates sem histórico/footguns e sem invariantes de ADR
        self.assertIn("rat.adr.money", self.a["reviewer"]["invariants"])
        self.assertIn("hist.fix.abc1234", self.a["reviewer"]["facts_used"])
        # security julga só regras de segurança (precedência: qualquer FAIL vence)
        self.assertEqual(self.a["security"]["gate_scope"], "security")
        self.assertNotIn("br.refund.window", self.a["security"]["invariants"])

    def test_deterministic(self):
        def raw():
            with open(sp_path(self.root, "team.json5"), "rb") as fh:
                return fh.read()
        b1 = raw()
        derive(self.root)
        self.assertEqual(b1, raw())

    def test_refuses_to_overwrite_cards(self):
        t = copy.deepcopy(self.team)
        t["agents"][0]["card"] = {"mission": "x"}
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        with self.assertRaises(CsError):
            derive(self.root)
        derive(self.root, force=True)

    def test_writes_only_inside_specialists(self):
        with self.assertRaises(CsError):
            write_json(self.root, os.path.join(self.root, "evil.json5"), {})


class PrefixAndLimitTest(unittest.TestCase):
    def test_repeated_prefix_is_consolidated(self):
        extra = {}
        for svc in ("payments-api", "payments-worker"):
            for f in ("a.py", "b.py", "c.py"):
                extra["src/%s/%s" % (svc, f)] = "x = 1\n"
        root = synth.make_repo(extra_files=extra)
        try:
            team, _ = derive(root)
            a = by_name(team)
            self.assertIn("dev-payments", a)
            self.assertEqual(sorted(a["dev-payments"]["territory"]), ["src/payments-api/**", "src/payments-worker/**"])
            self.assertTrue(validate(root)["pass"])
        finally:
            synth.cleanup(root)

    def test_at_most_eight_devs(self):
        extra = {}
        for i in range(10):
            for f in ("a.py", "b.py", "c.py", "d.py"):
                extra["mod%02d/%s" % (i, f)] = "x = 1\n"
        root = synth.make_repo(extra_files=extra)
        try:
            team, _ = derive(root)
            devs = [x for x in team["agents"] if x["name"].startswith(("dev-", "frontend")) and x["name"] != "dba"]
            self.assertLessEqual(len(devs), 8)
            self.assertGreaterEqual(len(devs), 3)
            self.assertTrue(validate(root)["pass"])
        finally:
            synth.cleanup(root)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.team, _ = derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def _with(self, mutate):
        t = copy.deepcopy(self.team)
        mutate(by_name(t))
        return validate(self.root, team=t)

    def test_derived_team_is_valid(self):
        out = validate(self.root)
        self.assertTrue(out["pass"], out)
        self.assertEqual(out["rules"]["3"]["coverage"], 1.0)

    def test_overlapping_territories_fail(self):
        out = self._with(lambda a: a["dev-orders"]["territory"].append("src/billing/**"))
        self.assertFalse(out["pass"])
        self.assertGreater(out["rules"]["3"]["overlaps"], 0)
        self.assertTrue(any("sobreposição" in e for e in out["rules"]["3"]["errors"]))

    def test_overlap_detected_by_expansion_not_strings(self):
        out = self._with(lambda a: a["dev-orders"]["territory"].append("src/*/invoice.py"))
        self.assertFalse(out["pass"])
        self.assertTrue(any("src/billing/invoice.py" in e for e in out["rules"]["3"]["errors"]))

    def test_uncovered_product_file_fails(self):
        out = self._with(lambda a: a["dev-catalog"].update(territory=["src/catalog/**"]))
        self.assertFalse(out["pass"])
        self.assertTrue(any("src/tiny/x.py" in e for e in out["rules"]["3"]["errors"]))

    def test_reserved_path_in_territory_fails(self):
        out = self._with(lambda a: a["ops"]["territory"].append(".claude/**"))
        self.assertTrue(any("reservado" in e for e in out["rules"]["3"]["errors"]))

    def test_name_and_kind_enum(self):
        def mut(a):
            a["po"]["name"] = "PO Bad"
            a["qa"]["kind"] = "tester"
        out = self._with(mut)
        self.assertEqual(out["rules"]["1"]["status"], "FAIL")
        self.assertEqual(out["rules"]["2"]["status"], "FAIL")

    def test_gate_with_write_tool_or_foreign_verdict_fails(self):
        def mut(a):
            a["reviewer"]["tools"] = a["reviewer"]["tools"] + ["Write"]
            a["security"]["card"] = {"mission": "Devolve APPROVED ou PASS."}
        out = self._with(mut)
        errs = " ".join(out["rules"]["2"]["errors"])
        self.assertIn("ferramenta de escrita", errs)
        self.assertIn("APPROVED", errs)

    def test_unknown_fact_fails(self):
        out = self._with(lambda a: a["dev-billing"]["facts_used"].append("nao.existe"))
        self.assertEqual(out["rules"]["4"]["status"], "FAIL")

    def test_invariant_missing_from_owner_fails(self):
        out = self._with(lambda a: a["dev-billing"].update(invariants=[]))
        self.assertEqual(out["rules"]["8"]["status"], "FAIL")
        out = self._with(lambda a: a["reviewer"].update(invariants=[]))
        self.assertEqual(out["rules"]["8"]["status"], "FAIL")

    def test_card_existence_and_size_in_final_stage(self):
        def mut(a):
            for x in a.values():
                x["card"] = {"mission": "m", "done_when": "`python3 -m unittest discover -s tests` sai 0",
                             "anchors": ["src/billing/invoice.py"]}
            a["dev-billing"]["card"]["anchors"].append("src/billing/nao_existe.py")
            a["dev-orders"]["card"]["knows"] = [{"text": "linha", "facts": []}] * 160
        out = self._with(mut)
        self.assertEqual(out["stage"], "final")
        self.assertTrue(any("nao_existe" in e for e in out["rules"]["5"]["errors"]))
        self.assertTrue(any("dev-orders" in e for e in out["rules"]["7"]["errors"]))
        self.assertTrue(any("bank.json5 ausente" in e for e in out["rules"]["6"]["errors"]))


class MapsTest(unittest.TestCase):
    def test_matrix_matches_graph_and_coupled_pair_collides(self):
        co = [{"a": "src/orders/checkout.py", "b": "src/billing/invoice.py", "support": 6,
               "conf_a_b": 0.8, "conf_b_a": 0.75}]
        root = synth.make_repo(cochange=co)
        try:
            derive(root)
            deps, col = build_maps(root)
            m = deps["matrix"]
            self.assertEqual(m["dev-orders"]["dev-billing"], 1)
            self.assertEqual(m["dev-billing"]["dev-shared"], 3)
            self.assertEqual(m["dev-catalog"]["dev-shared"], 1)
            self.assertEqual(deps["edges_cross_territory"], 7)
            ex = [p for p in deps["pairs"] if p["from"] == "dev-orders" and p["to"] == "dev-billing"][0]
            self.assertEqual(ex["examples"][0], {"file": "src/orders/checkout.py", "line": 1,
                                                 "imports": "src/billing/invoice.py"})
            pairs = [d["pair"] for d in col["do_not_parallelize"]]
            self.assertIn(["dev-billing", "dev-orders"], pairs)
            row = [r for r in col["pairs"] if r["pair"] == ["dev-billing", "dev-orders"]][0]
            self.assertIn("co-change", row["why"])
            self.assertEqual(deps["cycles"]["territory"], [])
        finally:
            synth.cleanup(root)

    def test_cycle_detected(self):
        root = synth.make_repo(extra_edges=[["src/billing/refund.py", "src/orders/order.py"]])
        try:
            derive(root)
            deps, _ = build_maps(root)
            cyc = deps["cycles"]["territory"]
            self.assertEqual([c["territories"] for c in cyc], [["dev-billing", "dev-orders"]])
            self.assertEqual(cyc[0]["path"][0], cyc[0]["path"][-1])
        finally:
            synth.cleanup(root)


class Json5Test(unittest.TestCase):
    def test_subset_roundtrip_and_rejection(self):
        txt = '// topo\n{a: 1, /* c */ "b": [1, 2,], c: {d: "x//y",},}\n'
        self.assertEqual(json5mini.loads(txt), {"a": 1, "b": [1, 2], "c": {"d": "x//y"}})
        obj = {"z": [1, {"k": "v"}], "a": None}
        self.assertEqual(json5mini.loads(json5mini.dumps(obj, "x")), obj)
        with self.assertRaises(ValueError):
            json5mini.loads("{a: 'x'}")

    def test_reads_plain_json_fallback(self):
        root = synth.make_repo(json_ext=".json")
        try:
            team, _ = derive(root)
            self.assertIn("dev-billing", by_name(team))
            self.assertEqual(read_json(sp_path(root, "team.json5"))["schema_version"], 1)
        finally:
            synth.cleanup(root)


if __name__ == "__main__":
    unittest.main()
