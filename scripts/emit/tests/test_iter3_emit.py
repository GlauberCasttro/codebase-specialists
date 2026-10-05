"""Iteração 3 — escrita fora de .swarm/ só com --allow-outside (contrato `emit_fora`), invariantes do gate
em arquivo (contrato `invariantes_gate`), budget --require-core (check de specialize.4) e plataformas do run."""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import fixture  # noqa: E402
from test_emit import ALL, run, snapshot  # noqa: E402
from emit import j5  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def p(self, rel):
        return Path(self.root) / rel


class Outside(Base):
    def test_emit_without_allow_outside_writes_nothing(self):
        def outside_snap():
            return {k: v for k, v in snapshot(self.root).items() if not k.startswith(".swarm")}
        before = outside_snap()
        code, out, err = run("--target", self.root, "--platforms", ALL)
        self.assertEqual(code, 3, out + err)
        self.assertIn("outside:", err)
        self.assertIn(".claude/agents/", err)
        self.assertIn("--allow-outside", err)
        self.assertEqual(outside_snap(), before)
        self.assertFalse(self.p(".swarm/emit/manifest.json5").exists())

    def test_dry_run_lists_outside_block(self):
        code, out, err = run("--target", self.root, "--platforms", ALL, "--dry-run")
        self.assertEqual(code, 0, err)
        block = out.split("outside:", 1)[1]
        self.assertIn("AGENTS.md", block)
        self.assertNotIn(".swarm/knowledge", block)  # dentro de .swarm/ não é "fora"

    def test_allow_outside_then_nothing_outside_left(self):
        self.assertEqual(run("--target", self.root, "--platforms", ALL, "--allow-outside")[0], 0)
        code, out, err = run("--target", self.root, "--platforms", ALL)  # nada muda fora: não precisa da flag
        self.assertEqual(code, 0, err)


class GateInvariantsFile(Base):
    def test_every_agent_with_invariants_gets_prioritized_file_and_gate_points_to_it(self):
        self.assertEqual(run("--target", self.root, "--platforms", ALL, "--allow-outside")[0], 0)
        team = j5.load(self.p(".swarm/team.json5"))
        gates = [a for a in team["agents"] if a.get("kind") == "gate" and a.get("invariants")]
        self.assertTrue(gates)
        for g in gates:
            data = j5.load(self.p(".swarm/knowledge/invariants/%s.json5" % g["name"]))
            self.assertEqual(data["total"], len(data["invariants"]))
            self.assertEqual([x["rank"] for x in data["invariants"]], list(range(1, data["total"] + 1)))
            self.assertFalse(any(":" in x["text"].split(" ")[0] and x["text"].split(":")[1][:1].isdigit()
                                 for x in data["invariants"]))
        self.assertEqual(run("validate", "--target", self.root, "--platforms", ALL)[0], 0)

    def test_truncated_gate_card_points_to_file(self):
        from emit import knowledge, render
        team = j5.load(self.p(".swarm/team.json5"))
        kn = knowledge.load(self.root)
        g = [a for a in team["agents"] if a.get("kind") == "gate"][0]
        g = dict(g, territory=[], invariants=list(kn.facts)[:30])
        body, _, _ = render.s1_card(team, g, kn, {"s2": None, "s4": None}, 1, 3)
        if render.invariant_count(g, kn.facts) > 3:
            self.assertIn(".swarm/knowledge/invariants/%s.json5" % g["name"], body)


class RequireCore(Base):
    def test_budget_require_core(self):
        # o check antigo (`emit budget`) passava com core escrito à mão no team.json5 (sem `team core ...`)
        code, out, err = run("budget", "--target", self.root, "--platforms", ALL)
        self.assertEqual(code, 0, err)
        code, out, err = run("budget", "--target", self.root, "--platforms", ALL, "--require-core")
        self.assertEqual(code, 1)
        self.assertIn("sem registro", err)
        t = j5.load(self.p(".swarm/team.json5"))
        rec = {"source": "set", "promoted": [{"text": l["text"]} for l in t["core"]["lines"]], "refused": []}
        (self.p(".swarm/panel")).mkdir(parents=True, exist_ok=True)
        self.p(".swarm/panel/core-promotion.json5").write_text(json.dumps(rec))
        self.assertEqual(run("budget", "--target", self.root, "--platforms", ALL, "--require-core")[0], 0)
        t["core"]["lines"].append({"text": "linha à mão", "facts": t["core"]["lines"][0]["facts"]})
        self.p(".swarm/team.json5").write_text(json.dumps(t))
        code, _, err = run("budget", "--target", self.root, "--platforms", ALL, "--require-core")
        self.assertEqual(code, 1)
        self.assertIn("editado à mão", err)


class RunPlatforms(Base):
    def test_validate_uses_run_platforms_over_stale_team(self):
        t = j5.load(self.p(".swarm/team.json5"))
        t["platforms"] = ["claude-code"]
        self.p(".swarm/team.json5").write_text(json.dumps(t))
        self.assertEqual(run("--target", self.root, "--platforms", "claude-code", "--allow-outside")[0], 0)
        self.assertEqual(run("validate", "--target", self.root)[0], 0)
        self.p(".swarm/run.json5").write_text(json.dumps({"platforms": ["claude-code", "cursor"]}))
        code, out, err = run("validate", "--target", self.root)
        self.assertEqual(code, 1, "validate tem de conferir as plataformas do run (cursor faltando)")
        self.assertIn(".cursor/", err)


if __name__ == "__main__":
    unittest.main()
