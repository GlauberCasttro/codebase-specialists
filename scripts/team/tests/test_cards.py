"""team approve|approved (specialize.2), team card set|revise e card-status (specialize.3, rt.4)."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402

CS = os.path.join(synth.SCRIPTS, "cs.py")


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def card(name):
    return {"description": "Use para mudar %s." % name, "mission": "Mantém %s correto." % name,
            "knows": [{"text": "Invoice é o termo canônico", "facts": ["gl.invoice"]}],
            "refuses": [{"text": "usar float para dinheiro", "why": "ADR 1", "facts": ["rat.adr.money"]}],
            "done_when": "`python3 -m unittest discover -s tests` sai 0",
            "playbooks": [{"title": "Teste", "steps": ["rode `python3 -m unittest discover -s tests`"]}],
            "rules": [], "footguns": [], "anchors": ["src/billing/invoice.py"]}


class CardsTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.team, _ = derive(self.root)
        self.names = [a["name"] for a in self.team["agents"]]

    def tearDown(self):
        synth.cleanup(self.root)

    def cardfile(self, name, obj=None):
        p = os.path.join(self.root, "tmp-%s.json5" % name)
        with open(p, "w") as fh:
            fh.write("// devolvido pelo subagente\n" + json.dumps({"card": obj or card(name)}))
        return p

    def set_all(self):
        for n in self.names:
            self.assertEqual(cs(self.root, "team", "card", "set", n, "--file", self.cardfile(n))[0], 0, n)

    def test_approve_then_roster_change_invalidates(self):
        self.assertEqual(cs(self.root, "team", "approved")[0], 1)
        self.assertEqual(cs(self.root, "team", "approve", "--by", "Ana", "--note", "ok")[0], 0)
        self.assertEqual(cs(self.root, "team", "approved")[0], 0)
        self.set_all()  # cartões não invalidam a aprovação
        self.assertEqual(cs(self.root, "team", "approved")[0], 0)
        t = read_json(sp_path(self.root, "team.json5"))
        t["agents"][0]["territory"] = t["agents"][0]["territory"] + ["src/extra/**"]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        code, _, err = cs(self.root, "team", "approved")
        self.assertEqual(code, 1)
        self.assertIn("roster mudou", err)
        self.assertEqual(cs(self.root, "team", "approve", "--by", " ")[0], 2)

    def test_card_set_validates_schema(self):
        bad = card("x")
        bad["refuses"][0].pop("why")
        bad["knows"][0]["facts"] = ["nao.existe"]
        code, _, err = cs(self.root, "team", "card", "set", self.names[0], "--file", self.cardfile("x", bad))
        self.assertEqual(code, 2)
        self.assertIn("sem porquê", err)
        self.assertIn("fato inexistente", err)
        self.assertEqual(cs(self.root, "team", "card", "set", "ninguem", "--file", self.cardfile("y"))[0], 2)
        gate = [a["name"] for a in self.team["agents"] if a["kind"] == "gate"][0]
        g = card(gate)
        g["mission"] = "Dá APPROVED quando ok"
        self.assertEqual(cs(self.root, "team", "card", "set", gate, "--file", self.cardfile("g", g))[0], 2)

    def test_all_drafted(self):
        self.assertEqual(cs(self.root, "team", "card-status", "--all-drafted")[0], 1)
        self.set_all()
        self.assertEqual(cs(self.root, "team", "card-status", "--all-drafted")[0], 0)
        t = read_json(sp_path(self.root, "team.json5"))
        self.assertEqual(t["agents"][0]["card"]["mission"], card(self.names[0])["mission"])
        self.assertIn("gl.invoice", t["agents"][0]["facts_used"])
        t["agents"][0]["card"]["mission"] = "editado à mão"
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        code, out, _ = cs(self.root, "team", "card-status", "--all-drafted")
        self.assertEqual(code, 1)
        self.assertIn("fora de `team card set", out)

    def test_revise_once_per_panel(self):
        self.set_all()
        n = self.names[0]
        self.assertEqual(cs(self.root, "team", "card", "revise", n, "--note", "x")[0], 2)  # sem painel
        for a in self.names:
            write_json(self.root, sp_path(self.root, "panel", "%s.json5" % a), {"agent": a, "verdict": "PASS"})
        self.assertEqual(cs(self.root, "team", "card", "revise", n)[0], 2)  # sem mudança e sem nota
        self.assertEqual(cs(self.root, "team", "card-status", "--all-revised")[0], 1)
        c2 = card(n)
        c2["mission"] = "Mantém cobrança correta (revisado)."
        self.assertEqual(cs(self.root, "team", "card", "revise", n, "--file", self.cardfile(n, c2))[0], 0)
        self.assertEqual(cs(self.root, "team", "card", "revise", n, "--note", "de novo")[0], 2)
        for a in self.names[1:]:
            self.assertEqual(cs(self.root, "team", "card", "revise", a, "--note", "sem objeção confirmada")[0], 0)
        self.assertEqual(cs(self.root, "team", "card-status", "--all-revised")[0], 0)
        self.assertEqual(cs(self.root, "team", "card-status", "--all-drafted")[0], 0)
        write_json(self.root, sp_path(self.root, "panel", "%s.json5" % n), {"agent": n, "verdict": "FAIL"})
        code, out, _ = cs(self.root, "team", "card-status", "--all-revised")
        self.assertEqual(code, 1)
        self.assertIn("re-consolidado", out)


if __name__ == "__main__":
    unittest.main()
