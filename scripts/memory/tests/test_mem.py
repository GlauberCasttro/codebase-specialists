"""Memória: BM25 (G8), fatos .json5, boost por path, stale, latência p95; autocorreção por agente (G15)."""
import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "tests"))
import fixture  # noqa: E402
from fixture import A  # noqa: E402
import mem  # noqa: E402
import j5  # noqa: E402

MEM = os.path.join(os.path.dirname(HERE), "mem.py")


def write_facts(root, name, items):
    with open(os.path.join(root, ".swarm", "facts", name), "w") as f:
        f.write(j5.dumps(items))


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)

    def tearDown(self):
        fixture.rm(self.root)

    def test_tokenizer_identifiers(self):
        self.assertIn("invoice", mem.tokenize("invoiceTotal"))
        self.assertEqual(set(mem.tokenize("invoice_total")) & set(mem.tokenize("InvoiceTotal")), {"invoice", "total", "invoicetotal"})
        self.assertEqual(mem.tokenize("Ação"), ["acao"])

    def test_camel_query_finds_snake_and_json5_facts(self):
        write_facts(self.root, "glossary.json5", [{"id": "term.x", "term": "calc_invoice_total", "scope": ["src/billing/**"]}])
        res = mem.search(self.root, "calcInvoiceTotal", k=3)
        self.assertEqual(res[0]["id"], "term.x")
        self.assertEqual(res[0]["kind"], "term")
        # fatos .json5 do fixture (business_rules.json5) também indexados
        self.assertIn("br.members.age", [r["id"] for r in mem.search(self.root, "usuário 18 anos", k=3)])

    def test_path_boost(self):
        write_facts(self.root, "more.json5", [
            {"id": "f.a", "claim": "cache de sessão expira", "scope": ["src/members/**"]},
            {"id": "f.b", "claim": "cache de sessão expira", "scope": ["src/billing/**"]}])
        self.assertEqual(mem.search(self.root, "cache sessão", paths=["src/billing/x.py"])[0]["id"], "f.b")
        self.assertEqual(mem.search(self.root, "cache sessão", paths=["src/members/x.py"])[0]["id"], "f.a")

    def test_stale_fact_not_returned(self):
        fp = mem.fingerprint(self.root, [{"file": "src/billing/total.py"}])
        write_facts(self.root, "rules2.json5", [{"id": "r.z", "claim": "zebra listrada", "evidence": [{"file": "src/billing/total.py"}],
                                                  "fingerprint": fp, "scope": ["src/billing/**"]}])
        self.assertTrue(mem.search(self.root, "zebra"))
        fixture.write(self.root, "src/billing/total.py", "mudou\n")
        mem.revalidate(self.root)
        self.assertFalse(mem.search(self.root, "zebra"))
        self.assertTrue(mem.search(self.root, "zebra", include_stale=True))

    def test_latency_p95_10k(self):
        mp = mem.mem_paths(self.root)
        os.makedirs(mp["dir"], exist_ok=True)
        rows = []
        words = ["pedido", "desconto", "fatura", "usuario", "sessao", "cache", "token", "imposto", "frete", "cupom", "estoque"]
        for i in range(10000):
            w = [words[(i * k) % len(words)] for k in (1, 3, 7)]
            rows.append({"id": "fact.%d" % i, "kind": "fact", "text": "regra %d sobre %s %s %s camelCase%dId" % (i, w[0], w[1], w[2], i),
                         "scope_paths": ["src/m%d/**" % (i % 50)], "status": "active"})
        mem.write_jsonl(mp["knowledge"], rows)
        mem.Index(self.root).ensure()
        lat = []
        for q in ["desconto cupom", "fatura imposto", "camelCase77Id", "usuario sessao token", "frete estoque"] * 8:
            t0 = time.time()
            res = mem.search(self.root, q, k=8, paths=["src/m7/x.py"])
            lat.append((time.time() - t0) * 1000)
            self.assertTrue(res)
        lat.sort()
        p95 = lat[int(len(lat) * 0.95) - 1]
        self.assertLess(p95, 200, "p95=%.1fms" % p95)
        self.assertEqual(mem.search(self.root, "camelCase77Id", k=1)[0]["id"], "fact.77")


class TestLessons(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        fixture.rm(self.root)

    def test_correction_injected_next_dispatch_same_scope(self):
        mem.correct(self.root, "dev-billing", "somar float", "somar centavos inteiros", "arredondamento",
                    paths=["src/billing/**"], evidence=["src/billing/total.py:1"])
        fixture.dispatched(self.root)
        import brief
        import engine
        import hcore
        ctx = engine.Ctx(self.root, hcore.load_board(self.root))
        pkg = brief.package(ctx, ctx.find("task", "T-1"), "implement")
        self.assertIn("centavos inteiros", pkg)
        self.assertEqual(mem.inject_lessons(self.root, "dev-billing", ["src/members/x.py"], ""), [])

    def test_check_lesson_fails_submission(self):
        mem.add_lesson(self.root, "dev-billing", "nunca use float em dinheiro", "centavos", ["src/billing/**"],
                       check="! grep -q float src/billing/discount.py", source="human")
        fixture.dispatched(self.root)
        fixture.write(self.root, "src/billing/discount.py", "x = float(1)\n")
        import cmds
        cmds.submit(self.root, "dev-billing", "T-1", {"files_changed": ["src/billing/discount.py"], "checks_run": ["x"],
                                                     "risks": [], "handoff_notes": ""})
        _, ev = cmds.verify(self.root, A, "T-1")
        self.assertTrue(any("lição" in p and "float" in p for p in ev[-1]["data"]["problems"]))
        chk = mem.check(self.root, "dev-billing", ["src/billing/discount.py"])
        self.assertTrue(chk["failed"])
        self.assertLessEqual(len(chk["checklist"]), 5)

    def test_second_occurrence_promotes_with_proposal(self):
        l1, c1 = mem.add_lesson(self.root, "dev-billing", "validar limite de desconto de 30 por cento", "regra de negócio",
                                ["src/billing/**"], source="review", evidence=[{"task": "T-1", "attempt": 1}])
        l2, c2 = mem.add_lesson(self.root, "dev-billing", "validar o limite de desconto de 30 por cento", "regra de negócio",
                                ["src/billing/**"], source="review", evidence=[{"task": "T-9", "attempt": 1}])
        self.assertFalse(c2)
        self.assertEqual(l2["status"], "promoted")
        pr = j5.load(mem.mem_paths(self.root)["promotions"])["promotions"]
        self.assertEqual(pr[0]["promoted_to"], "card-rule")
        self.assertIn("30 por cento", pr[0]["proposal"]["text"])
        # mesma ocorrência repetida não conta duas vezes
        l3, _ = mem.add_lesson(self.root, "dev-members", "x y z regra única", "w", [], source="review", evidence=[{"task": "T-2", "attempt": 1}])
        l4, _ = mem.add_lesson(self.root, "dev-members", "x y z regra única", "w", [], source="reject", evidence=[{"task": "T-2", "attempt": 1}])
        self.assertEqual((l4["count"], l4["status"]), (1, "active"))
        self.assertEqual(mem.inject_lessons(self.root, "dev-billing", ["src/billing/a.py"], "desconto"), [])

    def test_200_lessons_cap_and_budget(self):
        for i in range(200):
            mem.add_lesson(self.root, "dev-billing", "regra sintética número %d sobre módulo %d com detalhe %s" % (i, i, "q" * (i % 40)),
                           "porque %d" % i, ["src/billing/m%d.py" % (i % 7)], source="human")
        ls = mem.load_lessons(self.root, "dev-billing")
        self.assertLessEqual(sum(1 for l in ls if l["status"] == "active"), 30)
        inj = mem.inject_lessons(self.root, "dev-billing", ["src/billing/m3.py"], "regra")
        self.assertLessEqual(len(inj), 5)
        self.assertLessEqual(sum(len(l["rule"]) + len(l.get("why") or "") + 40 for l in inj), 1500)
        self.assertTrue(all(l["status"] == "active" for l in inj))

    def test_archived_and_stale_not_injected(self):
        l, _ = mem.add_lesson(self.root, "dev-billing", "nunca chame tax direto", "x", ["src/billing/**"], source="human",
                              evidence=[{"file": "src/billing/tax.py"}])
        fixture.write(self.root, "src/billing/tax.py", "RATE = 2\n")
        mem.revalidate_lessons(self.root)
        self.assertEqual(mem.inject_lessons(self.root, "dev-billing", ["src/billing/tax.py"], "tax"), [])
        l2, _ = mem.add_lesson(self.root, "dev-billing", "outra regra antiga qualquer", "x", ["src/billing/**"], source="human")
        ls = mem.load_lessons(self.root, "dev-billing")
        for x in ls:
            if x["id"] == l2["id"]:
                x["last_hit"] = "2020-01-01T00:00:00Z"
        mem.save_lessons(self.root, "dev-billing", ls)
        mem.archive_all(self.root)
        mem.archive_all(self.root)  # idempotente
        st = {x["id"]: x["status"] for x in mem.load_lessons(self.root, "dev-billing")}
        self.assertEqual(st[l2["id"]], "archived")
        self.assertEqual(mem.inject_lessons(self.root, "dev-billing", ["src/billing/a.py"], "regra antiga"), [])

    def test_auto_capture_review_fail_and_stats(self):
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        import cmds
        cmds.verify(self.root, A, "T-1")
        cmds.review(self.root, A, "T-1", "reviewer", "FAIL", "faltou validar desconto negativo em discount.py")
        ls = mem.load_lessons(self.root, "dev-billing")
        self.assertTrue(any("desconto negativo" in l["rule"] and l["source"] == "review" for l in ls))
        st = mem.lesson_stats(self.root)
        self.assertIn("recurrence_rate", st["dev-billing"])
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".swarm", "state", "memory", "agents", "dev-billing.json5")))

    def test_cli(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root)
        p = subprocess.run(["python3", MEM, "correct", "--agent", "dev-members", "--wrong", "idade 16", "--right", "idade 18",
                            "--why", "lei", "--paths", "src/members/**", "--evidence", "src/members/model.py:1"],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = subprocess.run(["python3", MEM, "inject", "--agent", "dev-members", "--paths", "src/members/model.py", "--json"],
                           env=env, stdout=subprocess.PIPE)
        self.assertEqual(len(json.loads(p.stdout)["lessons"]), 1)
        p = subprocess.run(["python3", MEM, "add", "--agent", "dev-members", "--kind", "lesson", "--rule", "use AGE", "--why", "x",
                            "--paths", "src/members/**"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, p.stderr)
        for c in (["archive"], ["stats"], ["search", "idade"], ["check", "--agent", "dev-members", "--files", "src/members/model.py"]):
            p = subprocess.run(["python3", MEM] + c, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(p.returncode, 0, (c, p.stderr))


if __name__ == "__main__":
    unittest.main()
