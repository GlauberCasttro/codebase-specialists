"""Regressões da iteração 1 no emissor: budget reporta todos os estouros; nada de gabarito (arquivo:linha, id de
fato com sha) nos artefatos; camadas S2/S5 do cartão usadas; precedência entre gates no cartão do gate; emissão
funciona sem painel consolidado (caminho rápido)."""
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
for p in (SCRIPTS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import fixture  # noqa: E402
from test_emit import ALL, run  # noqa: E402
from emit import j5  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def emit(self):
        return run("--target", self.root, "--platforms", ALL, "--allow-outside")

    def text(self, rel):
        return (Path(self.root) / rel).read_text(encoding="utf-8")


class TestBudgetAll(Base):
    def test_budget_reports_every_overflow(self):
        team = fixture.team()
        for i in (0, 1):
            team["agents"][i]["card"]["knows"] = [{"text": "fato %d" % k} for k in range(90)]
        fixture.write_team(self.root, team)
        code, out, err = run("budget", "--target", self.root, "--platforms", ALL)
        self.assertEqual(code, 1)
        self.assertIn("dev-billing", err)
        self.assertIn("dev-web", err)


class TestNoAnswerKeysInArtifacts(Base):
    def test_no_file_line_nor_fact_ids(self):
        team = fixture.team()
        team["agents"][0]["card"]["footguns"] = [{"text": "Cupom dobrou desconto", "facts": ["hist.fix.abc1234def56"]}]
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)
        for rel in (".claude/agents/dev-billing.md", ".claude/rules/cs-dev-billing.md", "src/billing/AGENTS.md",
                    ".claude/agents/reviewer.md"):
            if not (Path(self.root) / rel).is_file():
                continue
            t = self.text(rel)
            self.assertNotRegex(t, r"\.py:\d+", rel)
            self.assertNotIn("hist.fix", t, rel)
            self.assertNotIn("[conv.money.cents]", t, rel)
            self.assertNotRegex(t, r"\b[0-9a-f]{7,40}\b", rel)
        self.assertIn("Boleto", self.text(".claude/agents/dev-billing.md"))


class TestLayers(Base):
    def test_s2_and_s5_from_card_layers(self):
        team = fixture.team()
        team["agents"][0]["camadas"] = {
            "s0_core": [],
            "s2_por_caminho": [{"paths": ["src/billing/**"], "text": "Boleto nunca vence em feriado bancário",
                                "facts": ["rule.no-float-money"]}],
            "s5_memoria": [{"kind": "term", "text": "Cupom de frete é calculado depois do subtotal",
                            "facts": ["rule.no-float-money"]}]}
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)
        self.assertIn("feriado bancário", self.text(".claude/rules/cs-dev-billing.md"))
        mem = j5.loads(self.text(".swarm/knowledge/s5-memoria.json5"))
        self.assertEqual(mem["items"][0]["agent"], "dev-billing")
        self.assertIn("subtotal", mem["items"][0]["text"])
        code, out, err = run("validate", "--target", self.root, "--platforms", ALL)
        self.assertEqual(code, 0, err)


class TestGatePrecedenceAndFastPath(Base):
    def test_gate_card_states_precedence_and_no_panel_needed(self):
        self.assertFalse((Path(self.root) / ".swarm" / "panel").exists())
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)
        t = self.text(".claude/agents/reviewer.md")
        self.assertIn("qualquer `FAIL` vence", t)
        self.assertIn("NEEDS_SPECIALIST", t)


if __name__ == "__main__":
    unittest.main()


class TestBusinessRuleCoverage(unittest.TestCase):
    """Contrato novo do scan: data.test só com cobertura forte; resto em data.coverage + data.exercised_by."""

    def test_coverage_rendered_from_scan_fact(self):
        from emit import knowledge, render
        facts = [
            {"id": "br.a", "claim": "limite A", "evidence": [{"file": "src/a.go", "line": 3}],
             "data": {"coverage": "reference", "test": "src/a_test.go:11"}},
            {"id": "br.b", "claim": "limite B", "evidence": [{"file": "src/b.go", "line": 3}],
             "data": {"coverage": "exercised", "test": None, "exercised_by": "src/b_test.go:18"}},
            {"id": "br.c", "claim": "limite C", "evidence": [{"file": "src/c.go", "line": 3}],
             "data": {"coverage": "undetermined", "test": None}},
            {"id": "br.d", "claim": "limite D", "evidence": [{"file": "src/d.go", "line": 3}],
             "data": {"coverage": "none", "test": None}},
        ]
        lines = [render.brule_line(knowledge._norm_rule(f)) for f in facts]
        self.assertIn("teste: `src/a_test.go`", lines[0])
        self.assertIn("exercitada por `src/b_test.go`", lines[1])
        self.assertIn("cobertura indeterminada", lines[2])
        self.assertIn("sem teste", lines[3])
        for l in lines:
            self.assertNotRegex(l, r"\.go:\d+")


class TestReadOnlyQa(Base):
    def test_qa_without_territory_read_only_is_emitted(self):
        team = fixture.team()
        qa = [a for a in team["agents"] if a["name"] == "qa"][0]
        qa.update(kind="dev", territory=[], tools=["Read", "Grep", "Glob", "Bash"])
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 0, err)
        qa["tools"].append("Write")
        fixture.write_team(self.root, team)
        code, _, err = self.emit()
        self.assertEqual(code, 2)
        self.assertIn("ferramenta de escrita", err)


class TestFastPathMaps(unittest.TestCase):
    """Caminho rápido: emitir direto do team derivado (sem `team maps`/painel) não pode falhar por deps/colisão."""

    def test_emit_builds_missing_team_maps(self):
        sys.path.insert(0, os.path.join(SCRIPTS, "team", "tests"))
        import synth
        from team.derive import derive
        root = synth.make_repo()
        try:
            team, _ = derive(root)
            import json as _j
            from team._shared_tmp.common import sp_path, write_json
            for a in team["agents"]:
                a["card"] = {"description": "Use para %s." % a["name"], "mission": "Mantém %s." % a["name"],
                             "knows": [], "refuses": [], "done_when": "`python3 -m unittest discover -s tests` sai 0",
                             "playbooks": [], "rules": [], "footguns": [], "anchors": []}
            team["core"]["lines"] = [{"text": "Testes: `python3 -m unittest discover -s tests`",
                                      "facts": ["ops.test.unittest"]}]
            write_json(root, sp_path(root, "team.json5"), team)
            self.assertFalse(os.path.exists(sp_path(root, "knowledge", "deps.json5")))
            code, out, err = run("--target", root, "--platforms", ALL, "--allow-outside")
            self.assertNotIn("deps.json5", err)
            self.assertNotIn("collision.json5", err)
            self.assertTrue(os.path.exists(sp_path(root, "knowledge", "deps.json5")))
            self.assertTrue(os.path.exists(sp_path(root, "knowledge", "collision.json5")))
        finally:
            synth.cleanup(root)
