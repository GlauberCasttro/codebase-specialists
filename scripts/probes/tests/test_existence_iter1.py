"""Regressão iteração 1: falsos positivos da regra 5/G2 (existência) — e os verdadeiros continuam pegos."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.existence import existence_report  # noqa: E402


class ExistenceFalsePositives(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.team, _ = derive(self.root)
        p = os.path.join(self.root, ".swarm", "facts", "operations.json5")
        ops = read_json(p)
        ops["facts"].append(synth.fact("ops.make.test", "operations", "make test declarado",
                                       [{"file": "Makefile", "line": 1}], [],
                                       {"command": "make test", "status": "declared", "kind": "test"}))
        write_json(self.root, p, ops)
        os.makedirs(os.path.join(self.root, "src/billing/testdata"))
        with open(os.path.join(self.root, "src/billing/testdata/golden.json"), "w") as fh:
            fh.write("{}\n")

    def tearDown(self):
        synth.cleanup(self.root)

    def report(self, card):
        t = json.loads(json.dumps(self.team))
        for a in t["agents"]:
            if a["name"] == "dev-billing":
                a["card"] = card
        return existence_report(self.root, t)["agents"]["dev-billing"]["missing"]

    def test_false_positives_accepted(self):
        card = {
            "description": "Use para src/billing/**.", "mission": "Cobrança.",
            "knows": [
                {"text": "o web importa `@shop/api/*` e `@shop/shared` (workspaces npm, não caminhos)", "facts": []},
                {"text": "ADRs ficam em docs/**.", "facts": []},
                {"text": "a mensagem casa /invalid order transition/ no teste", "facts": []},
                {"text": "o cálculo fica em `billing/tax.py`, relativo ao território", "facts": []},
                {"text": "golden em `src/billing/testdata/golden.json` (fixture, fora do inventário)", "facts": []},
                {"text": "migrações seguem `db/migrations/NNN_*.sql`; pacotes em `src/*`", "facts": []},
                {"text": "manifestos `pyproject.toml/Makefile` mudam juntos", "facts": []},
            ],
            "rules": [{"text": "sem float em dinheiro", "check": "grep -rn 'float(' src/billing", "facts": []}],
            "done_when": "`make test` [unverified] sai 0 (toolchain ausente no scan)",
            "playbooks": [{"title": "teste", "steps": ["rode `make test` (não verificado) e `git diff --name-only`"]}],
            "anchors": ["src/billing/invoice.py"],
        }
        miss = self.report(card)
        self.assertEqual(miss, [], json.dumps(miss, ensure_ascii=False, indent=1))

    def test_true_positives_still_caught(self):
        card = {"description": "x", "mission": "y",
                "knows": [{"text": "ver `src/billing/nao_existe.py`", "facts": []}],
                "done_when": "`make deploy` [unverified] sai 0",
                "playbooks": [{"title": "t", "steps": ["rode `make lint`"]}],
                "anchors": ["src/billing/invoice.py"]}
        vals = sorted(m["value"] for m in self.report(card))
        self.assertIn("src/billing/nao_existe.py", vals)
        self.assertIn("make deploy", vals)  # [unverified] só vale para comando DECLARADO no repo
        self.assertIn("make lint", vals)


if __name__ == "__main__":
    unittest.main()


class ExistenceScanContract(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        self.team, _ = derive(self.root)
        p = os.path.join(self.root, ".swarm", "facts", "operations.json5")
        ops = read_json(p)
        ops["facts"].append(synth.fact("ops.test.make-test", "operations", "make test", [{"file": "Makefile", "line": 1}],
                                       [], {"command": "make test", "status": "unavailable", "kind": "test",
                                            "missing_tool": "go"}))
        write_json(self.root, p, ops)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_unavailable_command_and_package_refs(self):
        t = json.loads(json.dumps(self.team))
        for a in t["agents"]:
            if a["name"] == "dev-billing":
                a["card"] = {"description": "x", "mission": "y",
                             "knows": [{"text": "importa @shop/api/inventory e `@shop/shared/src`", "facts": []}],
                             "done_when": "`make test` sai 0 (go ausente no ambiente do scan)",
                             "anchors": ["src/billing/invoice.py"]}
        miss = existence_report(self.root, t)["agents"]["dev-billing"]["missing"]
        self.assertEqual(miss, [], miss)
