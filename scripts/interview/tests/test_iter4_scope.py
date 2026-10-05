"""Iteração 4 — `interview ask/record --scope` com vírgula (ts-shop, iteração 3): "a/**,b/**" virava UM glob
que não casava nada e a lacuna nunca chegava ao pacote de fatos do dono. Agora a CLI recusa e manda repetir a flag."""
import json
import os
import unittest

from helpers import cs, synth


class ScopeComma(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def log(self):
        p = os.path.join(self.root, ".swarm", "interview.jsonl")
        return open(p).read() if os.path.isfile(p) else ""

    def test_ask_refuses_comma_scope(self):
        code, out, err = cs(self.root, "interview", "ask", "--id", "Q-01", "--question", "Qual limite?",
                            "--scope", "src/billing/**,src/orders/**")
        self.assertEqual(code, 2, out + err)
        self.assertIn("repita a flag", err)
        self.assertEqual(self.log(), "")  # nada gravado (log é append-only)
        code, out, err = cs(self.root, "interview", "ask", "--id", "Q-01", "--question", "Qual limite?",
                            "--scope", "src/billing/**", "--scope", "src/orders/**")
        self.assertEqual(code, 0, err)
        rec = json.loads(self.log().splitlines()[0])
        self.assertEqual(rec["scope"], ["src/billing/**", "src/orders/**"])

    def test_record_refuses_comma_scope(self):
        code, out, err = cs(self.root, "interview", "record", "--id", "Q-09", "--question", "x?", "--answer-unknown",
                            "--scope", "a/**, b/**")
        self.assertEqual(code, 2, out + err)
        self.assertIn("repita a flag", err)


if __name__ == "__main__":
    unittest.main()
