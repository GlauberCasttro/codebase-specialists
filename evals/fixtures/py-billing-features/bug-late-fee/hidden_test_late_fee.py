"""Hidden oracle for the planted late-fee bug. NEVER copied to the target before grading.

fee = Money.percent(200) (2% fine, half-even) + half_even(cents * 100 * days / (30 * 10000)).
"""
import unittest

from billing.invoices.late_fees import late_fee
from billing.shared.money import Money

CASES = [
    (99999, 7, 2233),     # report from support: 2000 + 233
    (100000, 30, 3000),   # 2000 + 1000 (one full month)
    (12345, 45, 432),     # 247 + 185
    (300000, 1, 6100),    # 6000 + 100
    (1, 1, 0),
    (100000, 0, 0),
]


class HiddenLateFeeTest(unittest.TestCase):
    def test_cases(self):
        for cents, days, want in CASES:
            with self.subTest(cents=cents, days=days):
                self.assertEqual(late_fee(Money(cents), days).cents, want)


if __name__ == "__main__":
    unittest.main()
