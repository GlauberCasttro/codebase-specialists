"""Iteração 3 — pontuação: `@scope/pkg` em prosa não é arquivo extra; `NENHUM (caminho)` não é alucinação;
regra de config no cabeçalho vale pelo arquivo; duas respostas corretas; uma POR-QUÊ por ADR."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import Checker, is_none  # noqa: E402
from probes.generate import generate  # noqa: E402

EV = ["src/billing/invoice.py:3"]


class Scoring(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        self.ch = Checker(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def score(self, probe, answer, ev=EV):
        return self.ch.score_one(probe, {"answer": answer, "evidence": ev})

    def test_package_in_prose_is_not_extra_file(self):
        p = {"type": "dependency", "answer": {"exists": True, "files": ["src/orders/checkout.py"],
                                              "subject": "src/billing/invoice.py"}}
        ok, hall, why, _ = self.score(p, "src/orders/checkout.py (importa via @shop/shared e src/billing/invoice.py)")
        self.assertTrue(ok, why)

    def test_none_with_explanatory_path_is_negative(self):
        self.assertTrue(is_none("NENHUM (o comentário em apps/web/src/cart/cartStore.ts só menciona)"))
        p = {"type": "location", "answer": {"exists": False}}
        ok, hall, why, _ = self.score(p, "NENHUM (só aparece num comentário de src/billing/invoice.py)")
        self.assertTrue(ok, why)
        self.assertFalse(hall)

    def test_header_gabarito_accepts_rule_line(self):
        p = {"type": "prohibition", "answer": {"exists": True, "enforced_at": [{"file": "pyproject.toml", "line": 1}]}}
        ok, _, why, _ = self.score(p, "pyproject.toml:8", ["pyproject.toml:8"])
        self.assertTrue(ok, why)

    def test_two_correct_commands(self):
        p = {"type": "command", "answer": {"exists": True, "command": "make test",
                                           "alternatives": ["python3 -m unittest discover -s tests"]}}
        self.assertTrue(self.score(p, "`python3 -m unittest discover -s tests`")[0])
        self.assertTrue(self.score(p, "`make test`")[0])

    def test_generator_alternatives_and_one_why_per_adr(self):
        fd = sp_path(self.root, "facts")
        ops = read_json(os.path.join(fd, "operations.json5"))
        ops["facts"].append(synth.fact("ops.test.make", "operations", "make test", [{"cmd": "make test", "exit": 0}],
                                       [], {"command": "make test", "status": "verified", "kind": "test",
                                            "purpose": "a suíte de testes unitários"}))
        write_json(self.root, os.path.join(fd, "operations.json5"), ops)
        rat = read_json(os.path.join(fd, "rationale.json5"))
        for i in (1, 2, 3):
            rat["facts"].append(synth.fact("rat.adr.money.d%d" % i, "rationale", "decisão %d do ADR 1" % i,
                                           [{"file": "docs/adr/0001-money.md", "line": 3}], ["src/**"],
                                           {"topic": "decisão %d" % i, "key_terms": ["centavos"]}))
        write_json(self.root, os.path.join(fd, "rationale.json5"), rat)
        idx = read_json(os.path.join(fd, "index.json5"))
        idx["facts"] += ["ops.test.make", "rat.adr.money.d1", "rat.adr.money.d2", "rat.adr.money.d3"]
        write_json(self.root, os.path.join(fd, "index.json5"), idx)
        bank = generate(self.root)
        cmd = [p for p in bank["probes"] if p["type"] == "command" and p["answer"].get("alternatives")]
        self.assertTrue(cmd)
        for a in bank["agents"]:
            whys = [p for p in bank["probes"] if p["agent"] == a and p["type"] == "why"]
            files = [tuple(sorted(s["file"] for s in p["answer"]["sources"])) for p in whys]
            self.assertEqual(len(files), len(set(files)), "%s: POR-QUÊ redundante do mesmo ADR" % a)


if __name__ == "__main__":
    unittest.main()
