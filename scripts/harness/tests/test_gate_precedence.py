"""Regressão iteração 1: precedência entre gates sobre os mesmos caminhos era indefinida.
Regra: qualquer FAIL vence; NEEDS_SPECIALIST roteia para outro gate e é resolvido pelo veredito dele."""
import unittest

import fixture
from fixture import A
import cmds
import engine
import hcore
import views
from hcore import Refused


class TestGatePrecedence(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        fixture.dispatched(self.root)
        fixture.submit_ok(self.root)
        cmds.verify(self.root, A, "T-1")

    def tearDown(self):
        fixture.rm(self.root)

    def ctx(self):
        return engine.Ctx(self.root, hcore.load_board(self.root))

    def deleg(self):
        return engine.latest_deleg(hcore.find(hcore.load_board(self.root), "task", "T-1"))

    def test_fail_wins_over_pass(self):
        cmds.review(self.root, A, "T-1", "reviewer", "PASS", "ok discount.py:1")
        cmds.review(self.root, A, "T-1", "security", "FAIL", "segredo em discount.py:1")
        with self.assertRaises(Refused):
            cmds.accept(self.root, A, "T-1")
        task = hcore.find(hcore.load_board(self.root), "task", "T-1")
        self.assertEqual(engine.review_outcome(task), "FAIL")
        self.assertIn("reject", views.next_for(self.ctx(), "deleg", self.deleg()))

    def test_needs_specialist_routes_and_is_resolved_by_specialist(self):
        cmds.review(self.root, A, "T-1", "reviewer", "NEEDS_SPECIALIST", "toca credencial: security")
        task = hcore.find(hcore.load_board(self.root), "task", "T-1")
        self.assertEqual(engine.review_outcome(task), "NEEDS_SPECIALIST")
        nxt = views.next_for(self.ctx(), "deleg", self.deleg())
        self.assertIn("security", nxt)
        self.assertNotIn("reject", nxt)
        with self.assertRaises(Refused):
            cmds.accept(self.root, A, "T-1")
        cmds.review(self.root, A, "T-1", "security", "PASS", "sem segredo em discount.py:1")
        task = hcore.find(hcore.load_board(self.root), "task", "T-1")
        self.assertEqual(engine.review_outcome(task), "PASS")
        cmds.accept(self.root, A, "T-1")

    def test_specialist_fail_after_needs_specialist_blocks(self):
        cmds.review(self.root, A, "T-1", "reviewer", "NEEDS_SPECIALIST", "toca credencial: security")
        cmds.review(self.root, A, "T-1", "security", "FAIL", "segredo")
        task = hcore.find(hcore.load_board(self.root), "task", "T-1")
        self.assertEqual(engine.review_outcome(task), "FAIL")
        with self.assertRaises(Refused):
            cmds.accept(self.root, A, "T-1")


if __name__ == "__main__":
    unittest.main()
