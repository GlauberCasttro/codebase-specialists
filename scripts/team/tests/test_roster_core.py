"""Regressões da iteração 1: ajuste de roster por CLI, core.lines por comando, card set relativo ao alvo e
camadas persistidas."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from team._shared_tmp.common import expand, read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402

CS = os.path.join(synth.SCRIPTS, "cs.py")


def cs(root, *args, cwd=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=cwd or tempfile.gettempdir())
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def card(name):
    return {"description": "Use para mudar %s." % name, "mission": "Mantém %s correto." % name,
            "knows": [{"text": "Invoice é o termo canônico", "facts": ["gl.invoice"]}],
            "refuses": [{"text": "usar float para dinheiro", "why": "ADR 1", "facts": ["rat.adr.money"]}],
            "done_when": "`python3 -m unittest discover -s tests` sai 0",
            "playbooks": [], "rules": [], "footguns": [], "anchors": ["src/billing/invoice.py"]}


def team_of(root):
    return {a["name"]: a for a in read_json(sp_path(root, "team.json5"))["agents"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        os.makedirs(sp_path(self.root, "cards"), exist_ok=True)

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write("// teste\n" + json.dumps(obj))
        return rel


class CardSetTest(Base):
    def test_relative_file_resolves_against_target_and_camadas_persist(self):
        out = {"agent": "dev-billing", "card": card("dev-billing"),
               "camadas": {"s0_core": [{"text": "Dinheiro em centavos inteiros", "facts": ["rat.adr.money"]}],
                           "s2_por_caminho": [{"paths": ["src/billing/**"], "text": "reembolso só até 30 dias",
                                               "facts": ["br.refund.window"]}],
                           "s5_memoria": [{"kind": "term", "text": "Bill é variante proibida de Invoice",
                                           "facts": ["gl.invoice"]}]},
               "facts_used": ["gl.invoice"], "lacunas": ["x"], "injection_attempts": []}
        rel = self.put(".swarm/cards/dev-billing.draft.json5", out)
        code, o, e = cs(self.root, "team", "card", "set", "dev-billing", "--file", rel)  # cwd ≠ alvo
        self.assertEqual(code, 0, e)
        ag = team_of(self.root)["dev-billing"]
        self.assertEqual(ag["camadas"]["s2_por_caminho"][0]["paths"], ["src/billing/**"])
        self.assertEqual(ag["camadas"]["s0_core"][0]["facts"], ["rat.adr.money"])
        self.assertEqual(ag["camadas"]["s5_memoria"][0]["kind"], "term")
        self.assertNotIn("camadas", ag["card"])
        # alias --from (o nome que os prompts usam) e formato só-cartão continuam aceitos
        rel2 = self.put(".swarm/cards/dev-orders.json5", card("dev-orders"))
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-orders", "--from", rel2)[0], 0)
        # camada com fato inexistente é recusada
        out["camadas"]["s0_core"][0]["facts"] = ["nao.existe"]
        self.put(rel, out)
        code, _, e = cs(self.root, "team", "card", "set", "dev-billing", "--file", rel)
        self.assertEqual(code, 2)
        self.assertIn("nao.existe", e)


class CoreTest(Base):
    def test_core_set_validates_and_writes(self):
        rel = self.put(".swarm/core.json5", {"lines": [
            {"text": "Testes: `python3 -m unittest discover -s tests`", "facts": ["ops.test.unittest"]},
            {"text": "Dinheiro em centavos inteiros (ADR 1)", "facts": ["rat.adr.money"]}]})
        code, o, e = cs(self.root, "team", "core", "set", "--file", rel)
        self.assertEqual(code, 0, e)
        lines = read_json(sp_path(self.root, "team.json5"))["core"]["lines"]
        self.assertEqual(len(lines), 2)
        bad = self.put(".swarm/core-bad.json5", {"lines": [{"text": "sem fato", "facts": []}]})
        self.assertEqual(cs(self.root, "team", "core", "set", "--file", bad)[0], 2)
        many = self.put(".swarm/core-many.json5",
                        {"lines": [{"text": "linha %d" % i, "facts": ["rat.adr.money"]} for i in range(41)]})
        self.assertEqual(cs(self.root, "team", "core", "set", "--file", many)[0], 2)

    def test_core_from_panel_and_from_s0_core(self):
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            if a["name"] in ("dev-billing", "dev-orders"):
                a["camadas"] = {"s0_core": [{"text": "Dinheiro em centavos inteiros", "facts": ["rat.adr.money"]}]}
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        # caminho rápido: sem painel consolidado, usa os s0_core dos cartões
        code, o, e = cs(self.root, "team", "core", "from-panel")
        self.assertEqual(code, 0, e)
        lines = read_json(sp_path(self.root, "team.json5"))["core"]["lines"]
        self.assertEqual([l["facts"] for l in lines], [["rat.adr.money"]])
        write_json(self.root, sp_path(self.root, "panel", "core-candidates.json5"), {"schema_version": 1, "candidates": [
            {"facts": ["rules.lint.ruff-e"], "regras": ["ruff seleciona E em src"], "reviewers": ["a", "b"],
             "agents": ["dev-billing"]}]})
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        lines = read_json(sp_path(self.root, "team.json5"))["core"]["lines"]
        self.assertEqual(sorted(tuple(l["facts"]) for l in lines), [("rat.adr.money",), ("rules.lint.ruff-e",)])


class RosterTest(Base):
    def approve(self):
        self.assertEqual(cs(self.root, "team", "approve", "--by", "x")[0], 0)
        self.assertEqual(cs(self.root, "team", "approved")[0], 0)

    def assert_invalidated(self):
        code, _, e = cs(self.root, "team", "approved")
        self.assertEqual(code, 1, e)

    def test_move(self):
        self.approve()
        code, o, e = cs(self.root, "team", "roster", "move", "src/tiny/**", "--to", "dev-billing")
        self.assertEqual(code, 0, e)
        a = team_of(self.root)
        self.assertIn("src/tiny/**", a["dev-billing"]["territory"])
        self.assertNotIn("src/tiny/**", a["dev-catalog"]["territory"])
        self.assert_invalidated()
        self.assertNotEqual(cs(self.root, "team", "roster", "move", "nada/**", "--to", "dev-billing")[0], 0)
        self.assertNotEqual(cs(self.root, "team", "roster", "move", "src/tiny/**", "--to", "reviewer")[0], 0)

    def test_rename(self):
        self.approve()
        self.assertEqual(cs(self.root, "team", "roster", "rename", "frontend", "dev-web")[0], 0)
        a = team_of(self.root)
        self.assertIn("dev-web", a)
        self.assertNotIn("frontend", a)
        self.assert_invalidated()
        self.assertNotEqual(cs(self.root, "team", "roster", "rename", "dev-web", "dev-billing")[0], 0)
        self.assertNotEqual(cs(self.root, "team", "roster", "rename", "dev-web", "Dev Web")[0], 0)

    def test_add_and_remove(self):
        self.approve()
        code, o, e = cs(self.root, "team", "roster", "add", "dev-money", "--kind", "dev", "--territory",
                        "src/shared/money.py")
        self.assertEqual(code, 0, e)
        a = team_of(self.root)
        self.assertEqual(expand(a["dev-money"]["territory"], ["src/shared/money.py"]), ["src/shared/money.py"])
        self.assertFalse(expand(a["dev-shared"]["territory"], ["src/shared/money.py"]))
        self.assertIn("Edit", a["dev-money"]["tools"])
        self.assert_invalidated()
        self.assertNotEqual(cs(self.root, "team", "roster", "remove", "dev-money")[0], 0)  # tem território
        self.assertEqual(cs(self.root, "team", "roster", "remove", "dev-money", "--to", "dev-shared")[0], 0)
        a = team_of(self.root)
        self.assertNotIn("dev-money", a)
        self.assertEqual(a["dev-shared"]["territory"], ["src/shared/**"])

    def test_set_file(self):
        self.approve()
        t = read_json(sp_path(self.root, "team.json5"))
        roster = [{k: x[k] for k in ("name", "kind", "territory", "reads")} for x in t["agents"]]
        for r in roster:
            if r["name"] == "dev-catalog":
                r["territory"] = ["src/catalog/**"]
            if r["name"] == "dev-orders":
                r["territory"] = ["src/orders/**", "src/tiny/**"]
        rel = self.put(".swarm/roster.json5", {"agents": roster})
        code, o, e = cs(self.root, "team", "roster", "set", "--file", rel)
        self.assertEqual(code, 0, e)
        self.assertIn("src/tiny/**", team_of(self.root)["dev-orders"]["territory"])
        self.assert_invalidated()
        for r in roster:  # sobreposição → recusa sem gravar
            if r["name"] == "dev-catalog":
                r["territory"] = ["src/catalog/**", "src/tiny/**"]
        self.put(rel, {"agents": roster})
        code, _, e = cs(self.root, "team", "roster", "set", "--file", rel)
        self.assertNotEqual(code, 0)
        self.assertIn("sobreposição", e)
        self.assertEqual(team_of(self.root)["dev-catalog"]["territory"], ["src/catalog/**"])


if __name__ == "__main__":
    unittest.main()
