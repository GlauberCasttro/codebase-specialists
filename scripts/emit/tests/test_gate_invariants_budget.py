"""Gate com dezenas de invariantes cabe no S1: as prioritárias (ADR) ficam, o resto vira ponteiro (iteração 2, py-billing)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from emit import render  # noqa: E402


class InvariantPriorityTest(unittest.TestCase):
    def test_adr_first_and_limit(self):
        facts = {"brule.validation.a": "valida a", "rules.cfg.x": "config x", "rat.adr.0001": "centavos inteiros",
                 "rules.never.float": "nunca float"}
        agent = {"invariants": ["brule.validation.a", "rules.cfg.x", "rat.adr.0001", "rules.never.float", "sem.fato"]}
        self.assertEqual(render.invariant_lines(agent, facts, 2), ["- centavos inteiros", "- nunca float"])
        self.assertEqual(len(render.invariant_lines(agent, facts)), 4)
        self.assertEqual(render.invariant_count(agent, facts), 4)

    def test_rank_unknown_prefix_last(self):
        self.assertGreater(render._inv_rank("zzz.q"), render._inv_rank("rules.cfg.x"))


if __name__ == "__main__":
    unittest.main()
