import unittest
from datetime import date

from billing.invoices.late_fees import days_late, late_fee
from billing.shared.money import Money


class LateFeeTest(unittest.TestCase):
    def test_no_fee_when_not_overdue(self):
        self.assertEqual(late_fee(Money(100000), 0).cents, 0)
        self.assertEqual(days_late(date(2025, 5, 10), date(2025, 5, 1)), 0)

    def test_fine_and_one_day_of_interest(self):
        # 2% of R$ 3.000,00 = 6000; 1% a.m. / 30 * 1 day = 100
        self.assertEqual(late_fee(Money(300000), 1).cents, 6100)


if __name__ == "__main__":
    unittest.main()
