import unittest

from billing.shared.errors import CurrencyMismatch, InvalidAmount
from billing.shared.money import Money


class MoneyTest(unittest.TestCase):
    def test_rejects_float(self):
        with self.assertRaises(InvalidAmount):
            Money(10.5)

    def test_rejects_bool(self):
        with self.assertRaises(InvalidAmount):
            Money(True)

    def test_from_decimal_string_half_even(self):
        self.assertEqual(Money.from_decimal_string("10.005").cents, 1000)
        self.assertEqual(Money.from_decimal_string("10.015").cents, 1002)

    def test_percent_uses_half_even_without_float(self):
        # 5% ISS on R$ 0,10 = 0,5 cent -> rounds to even (0)
        self.assertEqual(Money(10).percent(500).cents, 0)
        self.assertEqual(Money(30).percent(500).cents, 2)
        self.assertEqual(Money(333).percent(3333).cents, 111)

    def test_allocate_never_loses_cents(self):
        parts = Money(100).allocate([1, 1, 1])
        self.assertEqual([p.cents for p in parts], [34, 33, 33])
        self.assertEqual(sum(p.cents for p in parts), 100)

    def test_currency_mismatch(self):
        with self.assertRaises(CurrencyMismatch):
            Money(1, "BRL") + Money(1, "USD")

    def test_format(self):
        self.assertEqual(Money(123456).format(), "R$ 1.234,56")
        self.assertEqual(Money(-5).format(), "-R$ 0,05")


if __name__ == "__main__":
    unittest.main()
