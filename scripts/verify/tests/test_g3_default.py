"""Regressão iteração 1: G3 sem --control ficava 'não medido'; agora usa evals/reference/generic-cards."""
import unittest

from helpers import synth

from team.derive import derive
from verify import gates as G


class G3Default(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_g3_measured_without_control(self):
        g = G.g3(self.root, "G3", None)
        self.assertNotIn("não medido", g["evidence"])
        self.assertIn("generic-cards", g["command"])


if __name__ == "__main__":
    unittest.main()
