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
from billing.shared.errors import PaymentDeclined, RefundExceedsCapture
from billing.shared.money import Money


class PaymentServiceTest(unittest.TestCase):
    def setUp(self):
        clock = FixedClock(datetime(2025, 7, 10, tzinfo=timezone.utc))
        self.invoices = InvoiceService(InMemoryInvoiceRepository(), InvoiceNumberer(), clock)
        self.journal = Journal(clock)
        self.gateway = FakeGateway()
        self.payments = PaymentService(self.gateway, self.invoices, self.journal)

    def _issued(self, cents, iss_bp=0):
        inv = self.invoices.create_draft("cus_9", iss_rate_bp=iss_bp)
        self.invoices.add_line(inv.id, "item", 1, Money(cents))
        self.invoices.issue(inv.id)
        return inv

    def test_capture_posts_balanced_entry(self):
        inv = self._issued(10000, iss_bp=500)
        self.payments.capture(inv.id, "tok_visa", "key-1")
        self.assertEqual(balance_of(self.journal, accounts.CASH), 10500)
        self.assertEqual(balance_of(self.journal, accounts.TAX_PAYABLE), -500)
        self.assertTrue(trial_balance_ok(self.journal))

    def test_capture_is_idempotent(self):
        inv = self._issued(2000)
        first = self.payments.capture(inv.id, "tok_visa", "key-1")
        again = self.payments.capture(inv.id, "tok_visa", "key-1")
        self.assertIs(first, again)
        self.assertEqual(self.gateway.calls, 1)
        self.assertEqual(len(self.journal.entries()), 1)

    def test_declined_posts_nothing(self):
        inv = self._issued(1013)
        with self.assertRaises(PaymentDeclined):
            self.payments.capture(inv.id, "tok_visa", "key-2")
        self.assertEqual(self.journal.entries(), [])

    def test_partial_refunds_cannot_exceed_capture(self):
        inv = self._issued(3000)
        pay = self.payments.capture(inv.id, "tok_visa", "key-3")
        self.payments.refund(pay.id, Money(1000))
        self.payments.refund(pay.id, Money(2000))
        with self.assertRaises(RefundExceedsCapture):
            self.payments.refund(pay.id, Money(1))
        self.assertEqual(balance_of(self.journal, accounts.CASH), 0)


if __name__ == "__main__":
    unittest.main()
