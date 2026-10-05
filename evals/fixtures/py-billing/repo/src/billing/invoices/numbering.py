"""Invoice numbers: INV-<year>-<6-digit sequence>, the sequence restarts every year.

Numbers are assigned at ``issue`` time, never at draft time: a voided draft must not
burn a number (fiscal requirement, gaps are audited).
"""
from typing import Dict


class InvoiceNumberer:
    def __init__(self) -> None:
        self._seq: Dict[int, int] = {}

    def next(self, year: int) -> str:
        current = self._seq.get(year, 0) + 1
        self._seq[year] = current
        return "INV-%d-%06d" % (year, current)
