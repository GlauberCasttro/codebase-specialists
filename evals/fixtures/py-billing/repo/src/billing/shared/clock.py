"""Injectable clock. Services never call datetime.now() directly."""
from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock requires an aware datetime (UTC)")
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance_days(self, days: int) -> None:
        from datetime import timedelta

        self._at = self._at + timedelta(days=days)
