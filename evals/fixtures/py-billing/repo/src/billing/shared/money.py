"""Money as integer cents.

Every monetary amount in billing is an ``int`` number of cents. ``float`` is never
accepted (see docs/adr/0001-money-as-integer-cents.md). Rounding is banker's
rounding (half-even), applied once, at the edge where a fraction appears.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List, Sequence

from billing.shared.errors import CurrencyMismatch, InvalidAmount

SUPPORTED_CURRENCIES = ("BRL", "USD", "EUR")
BASIS_POINTS = 10_000


def _div_half_even(numerator: int, denominator: int) -> int:
    """Integer division rounding half to even, without touching float."""
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str = "BRL"

    def __post_init__(self) -> None:
        if isinstance(self.cents, bool) or not isinstance(self.cents, int):
            raise InvalidAmount(
                "Money.cents must be int, got %s" % type(self.cents).__name__
            )
        if self.currency not in SUPPORTED_CURRENCIES:
            raise InvalidAmount("unsupported currency %s" % self.currency)

    @classmethod
    def zero(cls, currency: str = "BRL") -> "Money":
        return cls(0, currency)

    @classmethod
    def from_decimal_string(cls, value: str, currency: str = "BRL") -> "Money":
        quantized = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        return cls(int(quantized * 100), currency)

    def _same(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise InvalidAmount("cannot combine Money with %s" % type(other).__name__)
        if other.currency != self.currency:
            raise CurrencyMismatch("%s != %s" % (self.currency, other.currency))

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.cents - other.cents, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.cents, self.currency)

    def times(self, quantity: int) -> "Money":
        if not isinstance(quantity, int):
            raise InvalidAmount("quantity must be int")
        return Money(self.cents * quantity, self.currency)

    def percent(self, basis_points: int) -> "Money":
        """Apply a rate expressed in basis points (1% == 100 bp)."""
        return Money(_div_half_even(self.cents * basis_points, BASIS_POINTS), self.currency)

    def allocate(self, ratios: Sequence[int]) -> List["Money"]:
        """Split without losing cents (largest remainder goes first)."""
        total = sum(ratios)
        if total <= 0:
            raise InvalidAmount("ratios must sum to a positive number")
        shares = [self.cents * r // total for r in ratios]
        leftover = self.cents - sum(shares)
        for i in range(leftover):
            shares[i % len(shares)] += 1
        return [Money(s, self.currency) for s in shares]

    def is_zero(self) -> bool:
        return self.cents == 0

    def is_negative(self) -> bool:
        return self.cents < 0

    def format(self) -> str:
        sign = "-" if self.cents < 0 else ""
        units, cents = divmod(abs(self.cents), 100)
        symbol = {"BRL": "R$", "USD": "US$", "EUR": "EUR"}[self.currency]
        return "%s%s %s,%02d" % (sign, symbol, "{:,}".format(units).replace(",", "."), cents)
