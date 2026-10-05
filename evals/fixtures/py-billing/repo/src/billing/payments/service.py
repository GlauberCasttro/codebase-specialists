"""Capture and refund payments; every movement is mirrored in the ledger.

Captures are idempotent by ``idempotency_key`` (docs/adr/0003-idempotent-captures.md):
the gateway retries webhooks and clients retry on timeout, so a repeated key must
return the original payment and must NOT post a second journal entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from billing.invoices.service import InvoiceService
from billing.ledger import accounts
from billing.ledger.entries import credit, debit
from billing.ledger.journal import Journal
from billing.payments.refunds import check_refund
from billing.shared.errors import PaymentDeclined
from billing.shared.ids import new_id
from billing.shared.log import get_logger
from billing.shared.money import Money

log = get_logger(__name__)


@dataclass
class Payment:
    id: str
    invoice_id: str
    captured: Money
    refunded: Money
    gateway_ref: str
    capture_entry_id: str


class PaymentService:
    def __init__(self, gateway, invoices: InvoiceService, journal: Journal) -> None:
        self.gateway = gateway
        self.invoices = invoices
        self.journal = journal
        self._by_key: Dict[str, Payment] = {}
        self._by_id: Dict[str, Payment] = {}

    def capture(self, invoice_id: str, source: str, idempotency_key: str) -> Payment:
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        invoice = self.invoices.repo.get(invoice_id)
        amount = invoice.total
        result = self.gateway.charge(amount, source)
        if not result.approved:
            raise PaymentDeclined(result.reason or "declined")
        entry = self.journal.post(
            "capture %s" % invoice_id,
            [debit(accounts.CASH, amount),
             credit(accounts.REVENUE, invoice.subtotal),
             credit(accounts.TAX_PAYABLE, invoice.tax)],
        )
        payment = Payment(id=new_id("pay"), invoice_id=invoice_id, captured=amount,
                          refunded=Money.zero(amount.currency), gateway_ref=result.reference,
                          capture_entry_id=entry.id)
        self.invoices.mark_paid(invoice_id)
        self._by_key[idempotency_key] = payment
        self._by_id[payment.id] = payment
        log.info("payment captured", payment_id=payment.id, cents=amount.cents)
        return payment

    def refund(self, payment_id: str, amount: Money) -> Payment:
        payment = self._by_id[payment_id]
        check_refund(payment.captured, payment.refunded, amount)
        result = self.gateway.refund(payment.gateway_ref, amount)
        if not result.approved:
            raise PaymentDeclined("refund declined")
        self.journal.post(
            "refund %s" % payment_id,
            [debit(accounts.REVENUE, amount), credit(accounts.CASH, amount)],
        )
        payment.refunded = payment.refunded + amount
        return payment
