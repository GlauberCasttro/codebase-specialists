from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional

from billing.shared.money import Money


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


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
