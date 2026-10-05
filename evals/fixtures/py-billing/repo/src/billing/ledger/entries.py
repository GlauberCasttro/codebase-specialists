from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from billing.ledger import accounts
from billing.shared.errors import InvalidAmount
from billing.shared.money import Money


@dataclass(frozen=True)
class Posting:
    account: str
    debit: Money
    credit: Money

    def __post_init__(self) -> None:
        if self.account not in accounts.ALL:
            raise InvalidAmount("unknown account %s" % self.account)
        if self.debit.is_negative() or self.credit.is_negative():
            raise InvalidAmount("postings are never negative; reverse instead")


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    at: datetime
    memo: str
    postings: Tuple[Posting, ...]
    reverses: Optional[str] = None

    def total_debits(self) -> int:
        return sum(p.debit.cents for p in self.postings)

    def total_credits(self) -> int:
        return sum(p.credit.cents for p in self.postings)


def debit(account: str, amount: Money) -> Posting:
    return Posting(account, amount, Money.zero(amount.currency))


def credit(account: str, amount: Money) -> Posting:
    return Posting(account, Money.zero(amount.currency), amount)


# Deprecated alias from before ADR 0002; new code uses LedgerEntry.
JournalEntry = LedgerEntry
