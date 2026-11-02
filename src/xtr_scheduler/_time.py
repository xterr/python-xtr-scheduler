"""Reading dates the scheduler is given, and exact arithmetic on them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Final

from .exception import InvalidArgumentError

__all__ = [
    "EPOCH",
    "FAR_FUTURE",
    "aware",
    "from_microseconds",
    "microseconds",
    "seconds_between",
    "shifted",
]

EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)

#: Where a recurrence stops when told nothing else.
FAR_FUTURE: Final = datetime(3000, 1, 1, tzinfo=UTC)

_ONE_MICROSECOND: Final = timedelta(microseconds=1)


def aware(value: datetime | str, what: str) -> datetime:
    """Return ``value`` as a timezone-aware datetime, reading an ISO 8601 string.

    A date without a timezone means a different instant on every machine, so
    it is refused rather than guessed.

    Raises:
        InvalidArgumentError: If ``value`` is not a date, or has no timezone.
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidArgumentError(f'The {what} "{value}" is not an ISO 8601 date.') from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidArgumentError(f"The {what} {value.isoformat()} has no timezone.")
    return value


def microseconds(value: datetime) -> int:
    """Return ``value`` as whole microseconds since the epoch — exact, unlike a float."""
    return (value - EPOCH) // _ONE_MICROSECOND


def from_microseconds(value: int, zone: tzinfo | None) -> datetime:
    """Return the instant ``value`` microseconds after the epoch, shown in ``zone``."""
    return (EPOCH + timedelta(microseconds=value)).astimezone(zone)


def shifted(value: datetime, delta: timedelta) -> datetime:
    """Return the instant ``delta`` of elapsed time after ``value``, shown in ``value``'s zone.

    Not ``value + delta``: that moves the wall clock and drops ``fold``, so across
    the hour a clock goes back it lands an hour away from the instant meant.
    """
    return from_microseconds(microseconds(value) + delta // _ONE_MICROSECOND, value.tzinfo)


def seconds_between(start: datetime, end: datetime) -> float:
    """Return the seconds that pass from ``start`` to ``end``, negative when ``end`` is earlier.

    Not ``end - start``: two dates on one zone subtract by their wall clocks,
    which ignore ``fold``, so the hour a clock goes back would count as none.
    """
    return (microseconds(end) - microseconds(start)) / 1_000_000
