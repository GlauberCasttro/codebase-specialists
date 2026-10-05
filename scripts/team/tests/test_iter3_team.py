"""Iteração 3 — cartões (1.6 rascunho com identidade; revisão do refino), aprovação só de roster válido,
facts_used calculado na leitura (reads), `team facts`, categoria `example` com dono, gap citável."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
from test_roster_core import card, cs, team_of  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402


class Base(unittest.TestCase):
    extra = None

    def setUp(self):
        self.root = synth.make_repo(extra_files=self.extra)
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(json.dumps(obj))
        return rel


class DraftIdentity(Base):
    def draft(self, rel, at, mission):
        c = card("dev-billing")
        c["mission"] = mission
        return self.put(rel, {"agent": "dev-billing", "draft": {"id": "spec3-dev-billing-%s" % at[-2:], "at": at},
                              "card": c, "camadas": {}})

    def test_older_draft_refused(self):
        # iteração 2: redator repetido (atrasado) sobrescreveu o rascunho DEPOIS do card set
        new = self.draft(".swarm/tmp/cards/b2.json5", "2026-10-02T10:05:00Z", "versão nova")
        old = self.draft(".swarm/tmp/cards/b1.json5", "2026-10-02T10:00:00Z", "versão velha")
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", new)[0], 0)
        code, o, e = cs(self.root, "team", "card", "set", "dev-billing", "--file", old)
        self.assertEqual(code, 2, o + e)
        self.assertIn("MAIS VELHO", e)
        self.assertEqual(team_of(self.root)["dev-billing"]["card"]["mission"], "versão nova")
        st = read_json(sp_path(self.root, "cards", "status.json5"))["dev-billing"]["drafted"]
        self.assertEqual(st["draft_id"], "spec3-dev-billing-0Z")
        self.assertTrue(st["file_sha256"])
        # mesmo arquivo de novo: idempotente; --force grava o velho conscientemente
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", new)[0], 0)
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", old, "--force")[0], 0)

    def test_card_without_any_fact_is_not_drafted(self):
        c = card("dev-billing")
        c["knows"] = []
        c["refuses"] = [{"text": "nada", "why": "porque sim"}]
        self.put(".swarm/tmp/c.json5", c)
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/c.json5")[0], 0)
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertTrue(any("não cita nenhum fato" in p for p in row["problems_drafted"]))

    def test_knows_citing_only_gap_rejected(self):
        idx = read_json(sp_path(self.root, "facts", "index.json5"))
        idx["facts"].append("gap.q-01")
        write_json(self.root, sp_path(self.root, "facts", "index.json5"), idx)
        c = card("dev-billing")
        c["knows"] = [{"text": "não se sabe a política de estorno", "facts": ["gap.q-01"]}]
        c["refuses"].append({"text": "decidir política de estorno sozinho", "why": "lacuna declarada pelo dono",
                             "facts": ["gap.q-01"]})
        self.put(".swarm/tmp/g.json5", c)
        code, _, e = cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/g.json5")
        self.assertEqual(code, 2)
        self.assertIn("lacuna não é conhecimento", e)
        c["knows"] = []
        self.put(".swarm/tmp/g.json5", c)
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/g.json5")[0], 0)


class RefineRevision(Base):
    def test_refine_revision_allowed_after_failed_exam(self):
        self.put(".swarm/tmp/c.json5", card("dev-billing"))
        cs(self.root, "team", "card", "set", "dev-billing", "--file", ".swarm/tmp/c.json5")
        write_json(self.root, sp_path(self.root, "panel", "dev-billing.json5"), {"agent": "dev-billing"})
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "rt.4 ok")[0], 0)
        # iteração 2: validate.4 manda `team card revise` e a CLI recusava ("já revisou uma vez")
        code, _, e = cs(self.root, "team", "card", "revise", "dev-billing", "--note", "sem exame")
        self.assertEqual(code, 2)
        write_json(self.root, sp_path(self.root, "probes", "cycles.json5"),
                   {"dev-billing": [{"at": "x", "probes_sha256": "a", "answers_sha256": "b", "decision": "FAIL"}]})
        c = card("dev-billing")
        c["mission"] = "refinado"
        self.put(".swarm/tmp/r1.json5", c)
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file", ".swarm/tmp/r1.json5",
                        "--note", "validate.4 ciclo 1")
        self.assertEqual(code, 0, o + e)
        st = read_json(sp_path(self.root, "cards", "status.json5"))["dev-billing"]
        self.assertEqual(st["refines"][0]["cycle"], 1)
        self.assertIn("revised", st)
        # cartão revisado no refino continua "revisado" (rt.4 não reabre)
        from team.cards import card_status
        row = [r for r in card_status(self.root) if r["agent"] == "dev-billing"][0]
        self.assertEqual(row["problems_revised"], [])
        # o mesmo ciclo reprovado não libera uma segunda revisão
        self.assertEqual(cs(self.root, "team", "card", "revise", "dev-billing", "--note", "de novo")[0], 2)


class ApprovalNeedsValidRoster(Base):
    def break_coverage(self):
        full = os.path.join(self.root, "src", "novo", "mod.py")
        os.makedirs(os.path.dirname(full))
        with open(full, "w") as fh:
            fh.write("x = 1\n")
        inv = read_json(sp_path(self.root, "facts", "inventory.json5"))
        inv["files"].append({"path": "src/novo/mod.py", "class": "product"})
        write_json(self.root, sp_path(self.root, "facts", "inventory.json5"), inv)

    def test_approved_fails_when_roster_became_invalid(self):
        self.assertEqual(cs(self.root, "team", "approve", "--by", "ana")[0], 0)
        self.assertEqual(cs(self.root, "team", "approved")[0], 0)
        self.break_coverage()
        code, _, e = cs(self.root, "team", "approved")
        self.assertEqual(code, 1)
        self.assertIn("inválido", e)
        code, _, e = cs(self.root, "team", "approve", "--by", "ana")
        self.assertEqual(code, 2)


class FactsOnRead(Base):
    def test_reads_change_recomputes_facts_used_and_team_facts(self):
        t = team_of(self.root)
        before = set(t["dev-orders"]["facts_used"])
        self.assertNotIn("br.refund.window", before)
        roster = {"agents": [{"name": a["name"], "kind": a["kind"], "territory": a["territory"],
                              "reads": a.get("reads") or [] + (["src/billing/**"] if a["name"] == "dev-orders" else [])}
                             for a in read_json(sp_path(self.root, "team.json5"))["agents"]]}
        for r in roster["agents"]:
            if r["name"] == "dev-orders":
                r["reads"] = sorted(set(r["reads"]) | {"src/billing/**"})
        self.put(".swarm/tmp/roster.json5", roster)
        code, o, e = cs(self.root, "team", "roster", "set", "--file", ".swarm/tmp/roster.json5")
        self.assertEqual(code, 0, o + e)
        self.assertIn("br.refund.window", team_of(self.root)["dev-orders"]["facts_used"])
        code, o, e = cs(self.root, "team", "facts", "dev-orders", "--out", ".swarm/tmp/facts/dev-orders.json5")
        self.assertEqual(code, 0, e)
        doc = read_json(sp_path(self.root, "tmp", "facts", "dev-orders.json5"))
        self.assertIn("br.refund.window", [f["id"] for f in doc["facts"]])
        self.assertEqual(doc["agent"], "dev-orders")


class ExamplesOwnable(Base):
    extra = {"examples/partner/client.py": "def call():\n    return 1\n"}

    def setUp(self):
        Base.setUp(self)
        inv = read_json(sp_path(self.root, "facts", "inventory.json5"))
        for e in inv["files"]:
            if e["path"].startswith("examples/"):
                e["class"] = "example"
                e["category"] = "example"
        write_json(self.root, sp_path(self.root, "facts", "inventory.json5"), inv)

    def test_example_territory_accepted_and_not_required(self):
        from team._shared_tmp.factsio import Facts
        f = Facts(self.root)
        self.assertNotIn("examples/partner/client.py", f.product_files())
        self.assertIn("examples/partner/client.py", f.ownable_files())
        self.assertEqual(cs(self.root, "team", "validate", "--stage", "derive")[0], 0)  # exemplo sem dono: ok
        code, o, e = cs(self.root, "team", "roster", "add", "dev-partner", "--kind", "dev",
                        "--territory", "examples/**")
        self.assertEqual(code, 0, o + e)
        self.assertEqual(team_of(self.root)["dev-partner"]["territory"], ["examples/**"])
        self.assertEqual(cs(self.root, "team", "validate", "--stage", "derive")[0], 0)


if __name__ == "__main__":
    unittest.main()
