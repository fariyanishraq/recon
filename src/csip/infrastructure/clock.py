"""Clock abstraction: injectable time for deterministic tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class UtcClock:
    """System UTC clock for production wiring."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Deterministic clock for tests."""

    def __init__(self, fixed: datetime) -> None:
        if fixed.tzinfo is None:
            fixed = fixed.replace(tzinfo=UTC)
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed
