import copy
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402  (ajusta sys.path para scripts/)

from team._shared_tmp.common import CsError, read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.anticola import anticola_report  # noqa: E402
from probes.antitemplate import antitemplate_report  # noqa: E402
from probes.exam import baseline_filter, check, exam_pack  # noqa: E402
from probes.existence import existence_report  # noqa: E402
from probes.generate import generate, load_bank  # noqa: E402
from probes.memory_recall import memory_recall  # noqa: E402


def perfect(p):
    """Resposta correta + evidência existente para uma sonda (simula agente que sabe)."""
    a = p["answer"]
    if not a.get("exists", True):
        return {"id": p["id"], "answer": "NENHUM", "evidence": ["grep -rn x src"]}
    t = p["type"]
    if t == "location" or (t == "term" and a.get("variant") == "where"):
        loc = "%s:%d" % (a["path"], a["line"])
        return {"id": p["id"], "answer": loc, "evidence": [loc]}
    if t == "term":
        txt = a.get("canonical") or ", ".join(a.get("never_use") or [])
        return {"id": p["id"], "answer": txt, "evidence": ["src/billing/invoice.py:3"]}
    if t == "command":
        return {"id": p["id"], "answer": "`%s`" % a["command"], "evidence": [a["command"]]}
    if t in ("existence", "dependency"):
        return {"id": p["id"], "answer": ", ".join(a["files"]), "evidence": ["%s:1" % f for f in a["files"]]}
    if t == "history":
        return {"id": p["id"], "answer": a["sha"][:10], "evidence": ["git log --oneline"]}
    if t == "prohibition":
        loc = "%s:%d" % (a["enforced_at"][0]["file"], a["enforced_at"][0]["line"])
        return {"id": p["id"], "answer": loc, "evidence": [loc]}
    if t in ("business_rule", "why"):
        loc = "%s:%d" % (a["sources"][0]["file"], a["sources"][0]["line"])
        return {"id": p["id"], "answer": "%s em %s" % (a.get("value") or "", loc), "evidence": [loc]}
    raise AssertionError(t)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        self.bank = generate(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def probes(self, agent):
        return [p for p in load_bank(self.root)["probes"] if p["agent"] == agent]

    def answer(self, agent, items, kind="answers"):
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.%s.json5" % (agent, kind)), items)


class GenerateTest(Base):
    def test_shape_per_agent(self):
        for name, m in self.bank["agents"].items():
            self.assertEqual((m["territory"], m["cross"]), (12, 8), name)
            self.assertGreaterEqual(m["negatives"], 2, name)
        for p in self.bank["probes"]:
            for k in ("id", "agent", "type", "question", "answer", "atomic_facts"):
                self.assertIn(k, p)
            self.assertTrue(p["must_cite_evidence"])
            self.assertIsNone(p["discriminative"])

    def test_types_include_term_and_business_rule_with_negatives(self):
        ps = self.probes("dev-billing")
        types = set(p["type"] for p in ps)
        for t in ("location", "command", "dependency", "history", "why", "term", "business_rule", "prohibition"):
            self.assertIn(t, types)
        allp = self.bank["probes"]
        self.assertTrue(any(p["type"] == "term" and p["negative"] for p in allp))
        self.assertTrue(any(p["type"] == "business_rule" and p["negative"] for p in allp))
        br = [p for p in ps if p["type"] == "business_rule" and not p["negative"]][0]
        self.assertEqual(br["answer"]["sources"], [{"file": "src/billing/refund.py", "line": 4}])

    def test_location_question_hides_key_name(self):
        for p in self.bank["probes"]:
            if p["type"] == "location" and not p["negative"]:
                self.assertNotIn(p["answer"]["symbol"], p["question"])

    def test_fabricated_negatives_do_not_exist_in_repo(self):
        import re
        words = set()
        for dp, _, fs in os.walk(self.root):
            if ".swarm" in dp:
                continue
            for f in fs:
                with open(os.path.join(dp, f), errors="replace") as fh:
                    words.update(w.lower() for w in re.findall(r"[A-Za-z_]\w*", fh.read()))
        for p in self.bank["probes"]:
            m = re.search(r"símbolo `([^`]+)`", p["question"])
            if p["negative"] and m:
                self.assertNotIn(m.group(1).lower(), words)

    def test_deterministic_and_seeded(self):
        with open(sp_path(self.root, "probes", "bank.json5"), "rb") as fh:
            b1 = fh.read()
        generate(self.root)
        with open(sp_path(self.root, "probes", "bank.json5"), "rb") as fh:
            self.assertEqual(b1, fh.read())
        other = generate(self.root, seed="outra")
        self.assertNotEqual([p["question"] for p in other["probes"]], [p["question"] for p in self.bank["probes"]])

    def test_exam_pack_has_no_answers(self):
        path, pack = exam_pack(self.root, "dev-billing")
        self.assertTrue(path.endswith("dev-billing.questions.json5"))
        self.assertEqual(len(pack["questions"]), 20)
        for q in pack["questions"]:
            self.assertEqual(set(q), {"id", "type", "question"})
        with open(path) as fh:
            self.assertNotIn("abc1234def", fh.read())


class CheckTest(Base):
    def test_perfect_answers_need_baseline_delta(self):
        self.answer("dev-billing", [perfect(p) for p in self.probes("dev-billing")])
        rep = check(self.root, "dev-billing")
        self.assertEqual((rep["score_territory"], rep["score_cross"], rep["hallucinations"]), (1.0, 1.0, 0),
                         [r for r in rep["probes"] if not r["pass"]])
        self.assertEqual(rep["decision"], "FAIL")  # sem baseline, delta não medido
        self.assertTrue(any("baseline" in r for r in rep["reasons"]))
        self.answer("dev-billing", [{"id": p["id"], "answer": "NENHUM", "evidence": []}
                                    for p in self.probes("dev-billing")], kind="baseline")
        b = baseline_filter(self.root, "dev-billing")
        self.assertGreater(b["non_discriminative"], 0)  # negativas acertadas por chute
        rep = check(self.root, "dev-billing")
        self.assertEqual(rep["decision"], "PASS", rep["reasons"])
        self.assertGreater(rep["delta"], 0)
        self.assertEqual(rep["excluded_non_discriminative"], b["non_discriminative"])
        agg = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(agg["agents"]["dev-billing"]["decision"], "PASS")

    def test_hallucination_on_negative_vetoes(self):
        items = [perfect(p) for p in self.probes("dev-billing")]
        neg = [i for i, p in enumerate(self.probes("dev-billing")) if p["negative"]][0]
        items[neg] = {"id": items[neg]["id"], "answer": "Sim: src/billing/invoice.py:3",
                      "evidence": ["src/billing/invoice.py:3"]}
        self.answer("dev-billing", items)
        rep = check(self.root, "dev-billing")
        self.assertEqual(rep["hallucinations"], 1)
        self.assertEqual(rep["decision"], "FAIL")
        self.assertTrue(any("veto" in r for r in rep["reasons"]))

    def test_fabricated_evidence_is_hallucination(self):
        items = [perfect(p) for p in self.probes("dev-billing")]
        items[0]["evidence"] = ["src/billing/nao_existe.py:10"]
        self.answer("dev-billing", items)
        rep = check(self.root, "dev-billing")
        self.assertGreaterEqual(rep["hallucinations"], 1)

    def test_missing_evidence_fails_probe(self):
        items = [perfect(p) for p in self.probes("dev-billing")]
        items[0]["evidence"] = []
        self.answer("dev-billing", items)
        rep = check(self.root, "dev-billing")
        row = [r for r in rep["probes"] if r["id"] == items[0]["id"]][0]
        self.assertFalse(row["pass"])

    def test_location_line_tolerance(self):
        ps = self.probes("dev-billing")
        i = [k for k, p in enumerate(ps) if p["type"] == "location" and not p["negative"]][0]
        p = ps[i]
        for delta, expect in ((3, True), (4, False)):
            items = [perfect(x) for x in ps]
            loc = "%s:%d" % (p["answer"]["path"], max(1, p["answer"]["line"] + delta))
            items[i] = {"id": p["id"], "answer": loc, "evidence": ["%s:1" % p["answer"]["path"]]}
            self.answer("dev-billing", items)
            row = [r for r in check(self.root, "dev-billing")["probes"] if r["id"] == p["id"]][0]
            self.assertEqual(row["pass"], expect, (delta, row))

    def test_why_is_marked_for_panel_and_panel_overrides(self):
        self.answer("dev-billing", [perfect(p) for p in self.probes("dev-billing")])
        rep = check(self.root, "dev-billing")
        self.assertTrue(rep["panel_pending"])
        pid = rep["panel_pending"][0]
        write_json(self.root, sp_path(self.root, "probes", "panel", "dev-billing.json5"), {pid: "FAIL"})
        rep = check(self.root, "dev-billing")
        row = [r for r in rep["probes"] if r["id"] == pid][0]
        self.assertFalse(row["pass"])
        self.assertFalse(rep["provisional"])


class AnticolaTest(Base):
    def _team_with_card(self, text):
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            if a["name"] == "dev-orders":
                a["card"] = {"mission": "Cuida de pedidos.", "knows": [{"text": text, "facts": ["hist.fix.abc1234"]}]}
        return t

    def test_clean_card_passes_and_fact_ids_only_warn(self):
        t = self._team_with_card("Pedidos chamam a cobrança.")
        t["agents"][0]["facts_used"].append("hist.fix.abc1234")
        rep = anticola_report(self.root, team=t)
        self.assertTrue(rep["pass"], rep["violations"])
        self.assertTrue(rep["warnings"])

    def test_canonical_answers_in_card_fail(self):
        for txt, kind in (("Fatura definida em `src/billing/invoice.py:4`.", "path:line"),
                          ("Lint: rode `ruff check src` antes.", "command"),
                          ("A correção abc1234def mudou o arredondamento.", "sha")):
            rep = anticola_report(self.root, team=self._team_with_card(txt))
            self.assertFalse(rep["pass"], txt)
            self.assertIn(kind, set(v["kind"] for v in rep["violations"]))

    def test_extra_card_files_are_scanned(self):
        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, "dev-x.md"), "w") as fh:
                fh.write("veja src/billing/refund.py:4\n")
            rep = anticola_report(self.root, extra_paths=[d])
            self.assertFalse(rep["pass"])
        finally:
            import shutil
            shutil.rmtree(d)


class ExistenceAndTemplateTest(Base):
    def test_existence_ratio(self):
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            a["card"] = {"mission": "Edita `src/billing/invoice.py` e usa `Money`.",
                         "done_when": "`python3 -m unittest discover -s tests` sai 0",
                         "anchors": ["src/billing/tax.py"],
                         "rules": [{"text": "lint", "check": "ruff check src", "facts": []}]}
        rep = existence_report(self.root, t)
        self.assertEqual(rep["ratio"], 1.0, rep)
        self.assertTrue(rep["pass"])
        t["agents"][0]["card"]["anchors"].append("src/fantasma.py")
        t["agents"][0]["card"]["rules"].append({"text": "x", "check": "make deploy-prod", "facts": []})
        t["agents"][0]["card"]["mission"] += " Chama `NaoExisteHelper`."
        rep = existence_report(self.root, t)
        self.assertLess(rep["ratio"], 1.0)
        miss = set(m["value"] for m in rep["agents"][t["agents"][0]["name"]]["missing"])
        self.assertEqual(miss, {"src/fantasma.py", "make deploy-prod", "NaoExisteHelper"})

    def test_antitemplate(self):
        card = {"mission": "Cuida da cobrança neste repo.", "knows": [{"text": "Faturas usam Money em centavos"}],
                "done_when": "`python3 -m unittest discover -s tests` sai 0"}
        team = {"agents": [{"name": "dev-billing", "kind": "dev", "card": card}]}
        same = {"agents": [{"name": "dev-billing", "kind": "dev", "card": copy.deepcopy(card)}]}
        rep = antitemplate_report(team, same)
        self.assertFalse(rep["pass"])
        self.assertEqual(rep["agents"]["dev-billing"]["similarity"], 1.0)
        other = {"agents": [{"name": "dev-ledger", "kind": "dev", "card": {
            "mission": "Mantém o razão contábil do ERP.", "knows": [{"text": "Lançamentos são imutáveis após fechamento"}],
            "done_when": "`go test ./...` sai 0"}}]}
        rep = antitemplate_report(team, other)
        self.assertTrue(rep["pass"], rep)
        self.assertEqual(rep["agents"]["dev-billing"]["control_agent"], "dev-ledger")


FAKE_MEM = r'''
import json, sys
q = sys.argv[sys.argv.index("search") + 1]
ids = []
if "reembolso" in q: ids = ["br.refund.window"]
if "Invoice" in q or "Bill" in q or "cobrança" in q: ids = ["gl.invoice"]
print(json.dumps({"results": [{"id": i} for i in ids + ["x.1", "x.2"]], "ms": 3.0}))
'''


class MemoryRecallTest(Base):
    def test_recall_with_fake_search(self):
        d = tempfile.mkdtemp()
        try:
            mem = os.path.join(d, "mem.py")
            with open(mem, "w") as fh:
                fh.write(FAKE_MEM)
            rep = memory_recall(self.root, mem=mem)
            self.assertEqual(rep["recall_at_5"], 1.0, rep["misses"])
            self.assertTrue(rep["pass"])
            self.assertLess(rep["latency_p95_ms"], 200)
        finally:
            import shutil
            shutil.rmtree(d)

    def test_missing_search_is_clear_error(self):
        with self.assertRaises(CsError):
            memory_recall(self.root, mem="/nao/existe/mem.py")


if __name__ == "__main__":
    unittest.main()
