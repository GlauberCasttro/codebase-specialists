"""Regressão iteração 1: camadas.s5_memoria dos cartões se perdiam; agora o emissor grava
.swarm/knowledge/s5-memoria.json5 e cs-mem search encontra (S5)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "tests"))
import fixture  # noqa: E402
import mem  # noqa: E402
import j5  # noqa: E402


class TestS5Layer(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)

    def tearDown(self):
        fixture.rm(self.root)

    def test_search_finds_s5_items(self):
        k = os.path.join(self.root, ".swarm", "knowledge")
        os.makedirs(k, exist_ok=True)
        with open(os.path.join(k, "s5-memoria.json5"), "w") as fh:
            fh.write(j5.dumps({"schema_version": 1, "items": [
                {"id": "s5.dev-billing.1", "agent": "dev-billing", "kind": "rule",
                 "text": "estorno parcial exige aprovacaoDupla", "scope": ["src/billing/**"], "facts": ["x"]}]}))
        res = mem.search(self.root, "aprovacaoDupla estorno", k=3)
        self.assertTrue(res)
        self.assertEqual(res[0]["id"], "s5.dev-billing.1")
        self.assertEqual(res[0]["kind"], "rule")


if __name__ == "__main__":
    unittest.main()
