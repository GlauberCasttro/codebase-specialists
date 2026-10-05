"""Append-only double-entry journal (docs/adr/0002-ledger-append-only.md).

There is no update and no delete. A wrong entry is corrected by posting its
reversal with ``reverse``; both stay in the journal forever.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from billing.ledger.entries import LedgerEntry, Posting
from billing.shared.errors import ImmutableEntry, LedgerImbalance
from billing.shared.ids import new_id


class Journal:
    def __init__(self, clock) -> None:
        self.clock = clock
        self._entries: List[LedgerEntry] = []
        self._by_id: Dict[str, LedgerEntry] = {}
        self._reversed: Dict[str, str] = {}

    def post(self, memo: str, postings: Iterable[Posting]) -> LedgerEntry:
        entry = LedgerEntry(id=new_id("je"), at=self.clock.now(), memo=memo,
                             postings=tuple(postings))
        self._check_balanced(entry)
        self._append(entry)
        return entry

    def reverse(self, entry_id: str, memo: str = "") -> LedgerEntry:
        original = self._by_id[entry_id]
        if entry_id in self._reversed:
            raise ImmutableEntry("entry %s already reversed by %s" % (entry_id, self._reversed[entry_id]))
        swapped = tuple(Posting(p.account, p.credit, p.debit) for p in original.postings)
        entry = LedgerEntry(id=new_id("je"), at=self.clock.now(),
                             memo=memo or "reversal of %s" % entry_id,
                             postings=swapped, reverses=entry_id)
        self._check_balanced(entry)
        self._append(entry)
        self._reversed[entry_id] = entry.id
        return entry

    def entries(self) -> List[LedgerEntry]:
        return list(self._entries)

    def _append(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)
        self._by_id[entry.id] = entry

    @staticmethod
    def _check_balanced(entry: LedgerEntry) -> None:
        if not entry.postings:
            raise LedgerImbalance("entry without postings")
        if entry.total_debits() != entry.total_credits():
            raise LedgerImbalance(
                "debits %d != credits %d" % (entry.total_debits(), entry.total_credits())
            )
