"""Acceptance tests for FEAT accept-float-amounts. Approved: do not edit."""
import unittest

from billing.shared.money import Money


class FloatAmountsAcceptance(unittest.TestCase):
    def test_money_accepts_float_reais(self):
        self.assertEqual(Money(10.5).cents, 1050)

    def test_from_float(self):
        self.assertEqual(Money.from_float(19.99).cents, 1999)


if __name__ == "__main__":
    unittest.main()
