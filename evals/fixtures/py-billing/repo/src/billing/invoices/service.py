from __future__ import annotations

from datetime import timedelta

from billing.invoices.models import Invoice, InvoiceStatus, LineItem
from billing.invoices.numbering import InvoiceNumberer
from billing.invoices.repository import InMemoryInvoiceRepository
from billing.shared.errors import InvoiceStateError
from billing.shared.ids import new_id
from billing.shared.money import Money

DEFAULT_TERMS_DAYS = 30


class InvoiceService:
    def __init__(self, repo: InMemoryInvoiceRepository, numberer: InvoiceNumberer, clock) -> None:
        self.repo = repo
        self.numberer = numberer
        self.clock = clock

    def create_draft(self, customer_id: str, currency: str = "BRL", iss_rate_bp: int = 0) -> Invoice:
        invoice = Invoice(id=new_id("inv"), customer_id=customer_id, currency=currency,
                          iss_rate_bp=iss_rate_bp)
        self.repo.save(invoice)
        return invoice

    def add_line(self, invoice_id: str, description: str, quantity: int, unit_price: Money) -> Invoice:
        invoice = self._get(invoice_id)
        if invoice.status is not InvoiceStatus.DRAFT:
            raise InvoiceStateError("lines can only be added to drafts")
        if unit_price.currency != invoice.currency:
            raise InvoiceStateError("line currency differs from invoice currency")
        invoice.lines.append(LineItem(description, quantity, unit_price))
        self.repo.save(invoice)
        return invoice

    def issue(self, invoice_id: str, terms_days: int = DEFAULT_TERMS_DAYS) -> Invoice:
        invoice = self._get(invoice_id)
        if invoice.status is not InvoiceStatus.DRAFT:
            raise InvoiceStateError("only drafts can be issued")
        if not invoice.lines:
            raise InvoiceStateError("cannot issue an empty invoice")
        today = self.clock.now().date()
        invoice.number = self.numberer.next(today.year)
        invoice.due_date = today + timedelta(days=terms_days)
        invoice.transition_to(InvoiceStatus.ISSUED)
        self.repo.save(invoice)
        return invoice

    def mark_paid(self, invoice_id: str) -> Invoice:
        invoice = self._get(invoice_id)
        invoice.transition_to(InvoiceStatus.PAID)
        self.repo.save(invoice)
        return invoice

    def void(self, invoice_id: str) -> Invoice:
        invoice = self._get(invoice_id)
        invoice.transition_to(InvoiceStatus.VOID)
        self.repo.save(invoice)
        return invoice

    def _get(self, invoice_id: str) -> Invoice:
        invoice = self.repo.get(invoice_id)
        if invoice is None:
            raise InvoiceStateError("invoice %s not found" % invoice_id)
        return invoice
