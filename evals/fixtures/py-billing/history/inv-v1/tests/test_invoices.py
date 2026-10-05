import unittest
from datetime import date, datetime, timezone

from billing.invoices.models import InvoiceStatus
from billing.invoices.numbering import InvoiceNumberer
from billing.invoices.repository import InMemoryInvoiceRepository
from billing.invoices.service import InvoiceService
from billing.shared.clock import FixedClock
from billing.shared.errors import InvoiceStateError
from billing.shared.money import Money


def make_service(at=datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc)):
    clock = FixedClock(at)
    return InvoiceService(InMemoryInvoiceRepository(), InvoiceNumberer(), clock), clock


class InvoiceLifecycleTest(unittest.TestCase):
    def test_number_assigned_only_on_issue(self):
        svc, _ = make_service()
        inv = svc.create_draft("cus_1")
        self.assertIsNone(inv.number)
        svc.add_line(inv.id, "plan pro", 1, Money(9900))
        svc.issue(inv.id)
        self.assertEqual(inv.number, "INV-2025-000001")
        self.assertEqual(inv.due_date, date(2026, 1, 30))

    def test_sequence_restarts_each_year(self):
        svc, clock = make_service()
        a = svc.create_draft("cus_1")
        svc.add_line(a.id, "x", 1, Money(100))
        svc.issue(a.id)
        clock.advance_days(1)
        b = svc.create_draft("cus_1")
        svc.add_line(b.id, "y", 1, Money(100))
        svc.issue(b.id)
        self.assertEqual(b.number, "INV-2026-000001")

    def test_totals_with_iss(self):
        svc, _ = make_service()
        inv = svc.create_draft("cus_1", iss_rate_bp=500)
        svc.add_line(inv.id, "seat", 3, Money(1999))
        self.assertEqual(inv.subtotal.cents, 5997)
        self.assertEqual(inv.tax.cents, 300)
        self.assertEqual(inv.total.cents, 6297)

    def test_cannot_issue_empty(self):
        svc, _ = make_service()
        inv = svc.create_draft("cus_1")
        with self.assertRaises(InvoiceStateError):
            svc.issue(inv.id)

    def test_paid_invoice_cannot_be_voided(self):
        svc, _ = make_service()
        inv = svc.create_draft("cus_1")
        svc.add_line(inv.id, "x", 1, Money(100))
        svc.issue(inv.id)
        svc.mark_paid(inv.id)
        self.assertIs(inv.status, InvoiceStatus.PAID)
        with self.assertRaises(InvoiceStateError):
            svc.void(inv.id)

if __name__ == "__main__":
    unittest.main()
