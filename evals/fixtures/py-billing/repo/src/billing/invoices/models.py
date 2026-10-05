from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, FrozenSet, List, Optional

from billing.shared.errors import InvoiceStateError
from billing.shared.money import Money


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


# Invoice lifecycle: DRAFT -> ISSUED -> PAID | VOID. PAID and VOID are terminal.
# A PAID invoice is never voided: money goes back through a refund (payments).
ALLOWED_TRANSITIONS: Dict[InvoiceStatus, FrozenSet[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset({InvoiceStatus.ISSUED, InvoiceStatus.VOID}),
    InvoiceStatus.ISSUED: frozenset({InvoiceStatus.PAID, InvoiceStatus.VOID}),
    InvoiceStatus.PAID: frozenset(),
    InvoiceStatus.VOID: frozenset(),
}


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: int
    unit_price: Money

    @property
    def amount(self) -> Money:
        return self.unit_price.times(self.quantity)


@dataclass
class Invoice:
    id: str
    customer_id: str
    currency: str = "BRL"
    status: InvoiceStatus = InvoiceStatus.DRAFT
    number: Optional[str] = None
    due_date: Optional[date] = None
    iss_rate_bp: int = 0
    lines: List[LineItem] = field(default_factory=list)

    def transition_to(self, new_status: InvoiceStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvoiceStateError(
                "invalid invoice transition %s -> %s" % (self.status.value, new_status.value)
            )
        self.status = new_status

    @property
    def subtotal(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.amount
        return total

    @property
    def tax(self) -> Money:
        return self.subtotal.percent(self.iss_rate_bp)

    @property
    def total(self) -> Money:
        return self.subtotal + self.tax
