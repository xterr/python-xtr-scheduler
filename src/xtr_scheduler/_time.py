"""Reading dates the scheduler is given, and exact arithmetic on them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Final

from .exception import InvalidArgumentError

__all__ = ["EPOCH", "FAR_FUTURE", "aware", "from_microseconds", "microseconds"]

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
