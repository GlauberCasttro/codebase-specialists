"""Acceptance tests for FEAT refund-percent. Approved by the product owner: do not edit."""
import unittest
from datetime import datetime, timezone

from billing.invoices.numbering import InvoiceNumberer
from billing.invoices.repository import InMemoryInvoiceRepository
from billing.invoices.service import InvoiceService
from billing.ledger import accounts
from billing.ledger.balance import balance_of, trial_balance_ok
from billing.ledger.journal import Journal
from billing.payments.gateway import FakeGateway
from billing.payments.service import PaymentService
from billing.shared.clock import FixedClock
from billing.shared.errors import InvalidAmount, RefundExceedsCapture
from billing.shared.money import Money


class RefundPercentAcceptance(unittest.TestCase):
    def setUp(self):
        clock = FixedClock(datetime(2025, 10, 1, tzinfo=timezone.utc))
        self.invoices = InvoiceService(InMemoryInvoiceRepository(), InvoiceNumberer(), clock)
        self.journal = Journal(clock)
        self.gateway = FakeGateway()
        self.payments = PaymentService(self.gateway, self.invoices, self.journal)

    def _paid(self, cents, key):
        inv = self.invoices.create_draft("cus_acc")
        self.invoices.add_line(inv.id, "plan", 1, Money(cents))
        self.invoices.issue(inv.id)
        return self.payments.capture(inv.id, "tok_visa", key)

    def test_half_even_on_odd_cents(self):
        pay = self._paid(10001, "k1")
        self.payments.refund_percent(pay.id, 5000)   # 5000.5 -> 5000 (half-even)
        self.assertEqual(pay.refunded.cents, 5000)
        self.assertEqual(balance_of(self.journal, accounts.CASH), 5001)
        self.assertTrue(trial_balance_ok(self.journal))

    def test_successive_percentages_accumulate(self):
        pay = self._paid(10000, "k2")
        for _ in range(3):
            self.payments.refund_percent(pay.id, 3333)
        self.assertEqual(pay.refunded.cents, 9999)

    def test_rejects_non_integer_basis_points(self):
        pay = self._paid(10000, "k3")
        for bad in (12.5, True, 0, 10001):
            with self.assertRaises(InvalidAmount):
                self.payments.refund_percent(pay.id, bad)
        self.assertEqual(pay.refunded.cents, 0)

    def test_limit_refused_without_side_effects(self):
        pay = self._paid(10000, "k4")
        self.payments.refund(pay.id, Money(6000))
        calls, entries = self.gateway.calls, len(self.journal.entries())
        with self.assertRaises(RefundExceedsCapture):
            self.payments.refund_percent(pay.id, 5000)
        self.assertEqual(self.gateway.calls, calls)
        self.assertEqual(len(self.journal.entries()), entries)
        self.assertEqual(pay.refunded.cents, 6000)


if __name__ == "__main__":
    unittest.main()
