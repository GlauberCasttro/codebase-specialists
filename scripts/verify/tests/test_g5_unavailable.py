"""Contrato do scan: comando de teste `unavailable` (toolchain ausente) é declaração explícita para G5 — passa,
nunca como verified, e a evidência diz o que falta."""
import os
import unittest

from helpers import synth

from cslib import json5io
from cslib.paths import STATE_DIR
from verify import gates as G


class G5Unavailable(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def write_ops(self, status, missing=None):
        d = {"command": "make test", "kind": "test", "status": status}
        if missing:
            d["missing_tool"] = missing
        json5io.dump({"facts": [{"id": "ops.test.make-test", "claim": "make test", "data": d,
                                 "evidence": [{"file": "Makefile", "line": 1}]}],
                      "commands": [dict(d, cmd="make test")]},
                     os.path.join(self.root, STATE_DIR, "facts", "operations.json5"), "teste")

    def test_unavailable_counts_as_declaration(self):
        self.write_ops("unavailable", "go")
        g = G.g5(self.root, "G5")
        self.assertTrue(g["passed"], g)
        self.assertIn("toolchain ausente", g["evidence"])
        self.assertIn("go", g["evidence"])
        self.assertNotIn("verified", g["evidence"].split("(")[0])

    def test_failed_does_not_pass(self):
        self.write_ops("failed")
        self.assertFalse(G.g5(self.root, "G5")["passed"])


if __name__ == "__main__":
    unittest.main()
