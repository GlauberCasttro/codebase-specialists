"""Late fees on overdue invoices: 2% fine (multa) + 1% per month interest (juros), pro rata die.

Business rule (contract clause 7.2): fine = 2% of the invoice total, once; interest = 1% a month
over a 30-day month, proportional to the days late. Amounts are integer cents (ADR 0001).
"""
from __future__ import annotations

from datetime import date

from billing.shared.money import Money

LATE_FINE_BP = 200            # 2% fine, charged once
MONTHLY_INTEREST_BP = 100     # 1% a month
DAYS_PER_MONTH = 30           # commercial month


def days_late(due: date, today: date) -> int:
    return max(0, (today - due).days)


def late_fee(total: Money, days: int) -> Money:
    """Fine + pro rata interest for ``days`` days late (0 when not overdue)."""
    if days <= 0:
        return Money.zero(total.currency)
    fine = total.percent(LATE_FINE_BP)
    daily = Money(total.cents * MONTHLY_INTEREST_BP // (DAYS_PER_MONTH * 10_000), total.currency)
    interest = daily.times(days)
    return fine + interest
