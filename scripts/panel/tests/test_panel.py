"""cs.py panel (rt.1–rt.3): plano por adjacência, schema das objeções, confirmação mecânica, core, frescor."""
import json
import os
import unittest

from helpers import cs, synth, write

from cslib import json5io
from team._shared_tmp.common import read_json, sp_path, write_json
from team.derive import derive
from team.maps import build_maps

EMPTY = {"afirmacoes_sem_evidencia": [], "conflitos_com_meu_territorio": [], "regras_cross_cutting_faltando": []}


def basic_card(name, extra_knows=None, anchors=None):
    return {"description": "Use para %s." % name, "mission": "Mantém %s." % name,
            "knows": [{"text": "Invoice é o termo canônico", "facts": ["gl.invoice"]}] + (extra_knows or []),
            "refuses": [], "done_when": "`python3 -m unittest discover -s tests` sai 0", "playbooks": [],
            "rules": [], "footguns": [], "anchors": anchors or []}


class PanelTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        build_maps(self.root)
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            a["card"] = basic_card(a["name"])
        b = [a for a in t["agents"] if a["name"] == "dev-billing"][0]
        b["card"] = basic_card("dev-billing", extra_knows=[
            {"text": "Arredondamento usa float em todo o módulo", "facts": []},
            {"text": "Cobrança é chamada por src/orders/checkout.py", "facts": ["gl.invoice"]}],
            anchors=["src/billing/nao_existe.py", "src/billing/invoice.py"])
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        self.names = sorted(a["name"] for a in t["agents"])

    def tearDown(self):
        synth.cleanup(self.root)

    def plan(self):
        code, out, err = cs(self.root, "panel", "plan")
        self.assertEqual(code, 0, err)
        return json5io.load(sp_path(self.root, "panel", "plan.json5"))

    def record(self, agent, reviewer, obj):
        p = write(self.root, "tmp/%s-%s.json5" % (agent, reviewer), "// objeções\n" + json.dumps(obj))
        return cs(self.root, "panel", "record", agent, "--reviewer", reviewer, "--file", p)

    def fill(self, pl, overrides):
        for a, v in pl["agents"].items():
            for r in v["reviewers"]:
                code, _, err = self.record(a, r["name"], overrides.get((a, r["name"]), EMPTY))
                self.assertEqual(code, 0, err)

    def test_plan_two_adjacent_plus_skeptic(self):
        pl = self.plan()
        self.assertEqual(sorted(pl["agents"]), self.names)
        revs = pl["agents"]["dev-billing"]["reviewers"]
        self.assertEqual(len(revs), 3)
        self.assertEqual(revs[-1]["role"], "skeptic")
        adj = [r["name"] for r in revs if r["role"] == "adjacent"]
        self.assertIn("dev-orders", adj)  # checkout.py importa invoice.py
        self.assertNotIn("dev-billing", [r["name"] for r in revs])

    def test_plan_builds_missing_deps(self):
        # iteração 3: `panel plan` roda `team maps` quando deps.json5 falta (nenhum passo dizia para rodar)
        os.remove(sp_path(self.root, "knowledge", "deps.json5"))
        self.assertEqual(cs(self.root, "panel", "plan")[0], 0)
        self.assertTrue(os.path.isfile(sp_path(self.root, "knowledge", "deps.json5")))

    def test_record_schema_and_membership(self):
        pl = self.plan()
        r0 = pl["agents"]["dev-billing"]["reviewers"][0]["name"]
        self.assertEqual(self.record("dev-billing", r0, {"afirmacoes_sem_evidencia": []})[0], 2)
        bad = dict(EMPTY, regras_cross_cutting_faltando=[{"regra": "x", "facts": []}])
        self.assertEqual(self.record("dev-billing", r0, bad)[0], 2)
        outsider = [n for n in self.names if n not in [r["name"] for r in pl["agents"]["dev-billing"]["reviewers"]]
                    and n != "dev-billing"][0]
        self.assertEqual(self.record("dev-billing", outsider, EMPTY)[0], 2)
        self.assertEqual(self.record("dev-billing", r0, EMPTY)[0], 0)

    def test_status_consolidate_and_core_candidates(self):
        pl = self.plan()
        self.assertEqual(cs(self.root, "panel", "status", "--all-reviewed")[0], 1)
        self.assertEqual(cs(self.root, "panel", "consolidate")[0], 1)
        rule = {"regra": "Nunca float para dinheiro", "facts": ["rules.neg.no-float-money"]}
        ov = {("dev-billing", "dev-orders"): {
                  "afirmacoes_sem_evidencia": [{"afirmacao": "âncora inexistente", "ref": "src/billing/nao_existe.py"},
                                               {"afirmacao": "invoice existe?", "ref": "src/billing/invoice.py"}],
                  "conflitos_com_meu_territorio": [{"path": "src/orders/checkout.py", "descricao": "é meu"},
                                                   {"path": "src/catalog/price.py", "descricao": "não é meu"}],
                  "regras_cross_cutting_faltando": [rule, {"regra": "fantasma", "facts": ["nao.existe"]}]},
              ("dev-billing", "cetico"): dict(EMPTY, afirmacoes_sem_evidencia=[
                  {"afirmacao": "arredondamento usa float em todo o módulo"}],
                  regras_cross_cutting_faltando=[rule])}
        self.fill(pl, ov)
        self.assertEqual(cs(self.root, "panel", "status", "--all-reviewed")[0], 0)
        self.assertEqual(cs(self.root, "panel", "consolidate", "--check")[0], 1)
        code, out, err = cs(self.root, "panel", "consolidate")
        self.assertEqual(code, 0, err)
        doc = json5io.load(sp_path(self.root, "panel", "dev-billing.json5"))
        self.assertEqual(doc["verdict"], "FAIL")
        aff = doc["confirmed"]["afirmacoes_sem_evidencia"]
        self.assertEqual(sorted(x.get("ref", "") for x in aff), ["", "src/billing/nao_existe.py"])
        self.assertEqual([x["path"] for x in doc["confirmed"]["conflitos_com_meu_territorio"]],
                         ["src/orders/checkout.py"])
        self.assertEqual(len(doc["confirmed"]["regras_cross_cutting_faltando"]), 2)
        self.assertEqual(sorted(x["tipo"] for x in doc["rejected"]),
                         ["afirmacoes_sem_evidencia", "conflitos_com_meu_territorio", "regras_cross_cutting_faltando"])
        cc = json5io.load(sp_path(self.root, "panel", "core-candidates.json5"))
        self.assertEqual([c["facts"] for c in cc["candidates"]], [["rules.neg.no-float-money"]])
        other = json5io.load(sp_path(self.root, "panel", "dev-orders.json5"))
        self.assertEqual(other["verdict"], "PASS")
        self.assertEqual(cs(self.root, "panel", "consolidate", "--check")[0], 0)
        # revisão nova depois da consolidação → check falha
        self.record("dev-orders", pl["agents"]["dev-orders"]["reviewers"][0]["name"], dict(EMPTY, regras_cross_cutting_faltando=[rule]))
        self.assertEqual(cs(self.root, "panel", "consolidate", "--check")[0], 1)

    def test_single_reviewer_rule_is_not_core(self):
        pl = self.plan()
        rule = {"regra": "Nunca float", "facts": ["rules.neg.no-float-money"]}
        self.fill(pl, {("dev-billing", "cetico"): dict(EMPTY, regras_cross_cutting_faltando=[rule])})
        cs(self.root, "panel", "consolidate")
        cc = json5io.load(sp_path(self.root, "panel", "core-candidates.json5"))
        self.assertEqual(cc["candidates"], [])

    def test_roster_change_invalidates_plan(self):
        self.plan()
        t = read_json(sp_path(self.root, "team.json5"))
        t["agents"] = t["agents"][1:]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        self.assertEqual(cs(self.root, "panel", "status", "--all-reviewed")[0], 1)


class WhyPanelTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        from probes.generate import generate
        self.bank = generate(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_why_verdict_in_probes_format(self):
        why = [p for p in self.bank["probes"] if p["type"] == "why"][0]
        other = [p for p in self.bank["probes"] if p["type"] == "location" and p["agent"] == why["agent"]][0]
        self.assertEqual(cs(self.root, "panel", "why", why["agent"], "--probe", other["id"], "--verdict", "PASS")[0], 2)
        code, _, err = cs(self.root, "panel", "why", why["agent"], "--probe", why["id"], "--verdict", "FAIL")
        self.assertEqual(code, 0, err)
        doc = json5io.load(sp_path(self.root, "probes", "panel", "%s.json5" % why["agent"]))
        self.assertEqual(doc[why["id"]]["verdict"], "FAIL")  # iteração 3: + identidade da sonda
        from probes.generate import probe_sha
        self.assertEqual(doc[why["id"]]["probe_sha256"], probe_sha(why))


if __name__ == "__main__":
    unittest.main()
