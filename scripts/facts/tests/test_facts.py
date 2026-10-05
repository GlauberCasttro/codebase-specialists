"""cs.py facts spotcheck (scan.5): registro, correção llm_interpretation e check --min."""
import os
import unittest

from helpers import cs, synth

from cslib import json5io
from cslib.paths import STATE_DIR


class SpotcheckTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def rec(self, fact, verdict="ok", note="conferido no código"):
        return cs(self.root, "facts", "spotcheck", "record", "--fact", fact, "--verdict", verdict, "--note", note)

    def test_min_reached_passes(self):
        self.assertEqual(cs(self.root, "facts", "spotcheck", "--min", "2")[0], 1)
        for f in ("gl.invoice", "br.refund.window"):
            self.assertEqual(self.rec(f)[0], 0)
        code, out, _ = cs(self.root, "facts", "spotcheck", "--min", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual(cs(self.root, "facts", "spotcheck", "--min", "3")[0], 1)

    def test_same_fact_counts_once(self):
        self.rec("gl.invoice")
        self.rec("gl.invoice")
        self.assertEqual(cs(self.root, "facts", "spotcheck", "--min", "2")[0], 1)

    def test_unknown_fact_and_bad_input_exit_2(self):
        self.assertEqual(self.rec("nao.existe")[0], 2)
        self.assertEqual(cs(self.root, "facts", "spotcheck", "--min", "0")[0], 2)
        self.assertEqual(cs(self.root, "facts", "spotcheck")[0], 2)

    def test_wrong_requires_correction(self):
        code, _, err = self.rec("hist.fix.abc1234", "wrong", "o fix foi em refund, não em tax")
        self.assertEqual(code, 2)
        self.assertIn("facts interpret", err)
        code, out, err = cs(self.root, "facts", "interpret", "--id", "fix-refund", "--claim",
                            "O fix de arredondamento tocou src/billing/refund.py", "--supports", "gl.invoice",
                            "--evidence", "src/billing/refund.py:4", "--corrects", "hist.fix.abc1234")
        self.assertEqual(code, 0, err)
        doc = json5io.load(os.path.join(self.root, STATE_DIR, "facts", "interpretation.json5"))
        f = doc["facts"][0]
        self.assertEqual((f["id"], f["origin"], f["data"]["corrects"]),
                         ("interp.fix-refund", "llm_interpretation", "hist.fix.abc1234"))
        idx = json5io.load(os.path.join(self.root, STATE_DIR, "facts", "index.json5"))
        self.assertIn("interp.fix-refund", idx["facts"])
        self.assertEqual(self.rec("hist.fix.abc1234", "wrong", "corrigido")[0], 0)
        self.rec("gl.invoice")
        self.assertEqual(cs(self.root, "facts", "spotcheck", "--min", "2")[0], 0)

    def test_wrong_without_correction_in_log_fails_check(self):
        cs(self.root, "facts", "interpret", "--id", "x", "--claim", "c", "--supports", "gl.invoice",
           "--evidence", "src/billing/refund.py:4", "--corrects", "gl.invoice")
        self.rec("gl.invoice", "wrong", "errado")
        os.remove(os.path.join(self.root, STATE_DIR, "facts", "interpretation.json5"))
        code, _, err = cs(self.root, "facts", "spotcheck", "--min", "1")
        self.assertEqual(code, 1)
        self.assertIn("sem fato llm_interpretation", err)

    def test_interpret_validates(self):
        base = ["facts", "interpret", "--id", "y", "--claim", "c"]
        self.assertEqual(cs(self.root, *(base + ["--supports", "nada", "--evidence", "README.md:1"]))[0], 2)
        self.assertEqual(cs(self.root, *(base + ["--supports", "gl.invoice", "--evidence", "README.md:99"]))[0], 2)
        self.assertEqual(cs(self.root, *(base + ["--supports", "gl.invoice", "--evidence", "../x:1"]))[0], 2)


if __name__ == "__main__":
    unittest.main()
