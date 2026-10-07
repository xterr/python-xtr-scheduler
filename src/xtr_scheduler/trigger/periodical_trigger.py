"""Runs at a fixed interval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, final

from typing_extensions import override
from xtr_clock import shift_calendar

from xtr_scheduler._time import (
    EPOCH,
    FAR_FUTURE,
    aware,
    from_microseconds,
    microseconds,
)
from xtr_scheduler.exception import InvalidArgumentError

from .stateful_trigger_interface import StatefulTriggerInterface

__all__ = ["PeriodicalTrigger"]

_MICROSECONDS_PER_SECOND: Final = 1_000_000

_ISO_DURATION: Final = re.compile(
    r"^P(?!$)(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?"
    r"(?:T(?=\d)(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)
_RELATIVE: Final = re.compile(
    r"^\s*(\d+)\s*(sec|second|min|minute|hour|day|week|fortnight|month|year)s?\s*$",
    re.IGNORECASE,
)
_SECONDS_PER_UNIT: Final = {"sec": 1, "second": 1, "min": 60, "minute": 60, "hour": 3600}
_DAYS_PER_UNIT: Final = {"day": 1, "week": 7, "fortnight": 14}
_MONTHS_PER_UNIT: Final = {"month": 1, "year": 12}


@dataclass(frozen=True, slots=True)
class _CalendarStep:
    """A step that is not a fixed number of seconds: months, and days across clock changes."""

    months: int
    days: int


@final
class PeriodicalTrigger(StatefulTriggerInterface):
    """Runs every ``interval``, counted from ``from_``, until ``until``.

    The interval is seconds (``3600``, ``"3600"``), a :class:`~datetime.timedelta`,
    an ISO 8601 duration (``"PT1H"``, ``"P1D"`` — always converted to
    seconds), or ``"<n> <unit>"`` with a unit from ``second``/``sec``,
    ``minute``/``min``, ``hour``, ``day``, ``week``, ``fortnight``, ``month``
    and ``year``, plural or not.

    Seconds, minutes and hours are exact: runs fall exactly that far apart,
    counted from ``from_``. Days, weeks, months and years follow the calendar
    of ``from_``'s timezone instead — "every day" at 09:00 stays at 09:00
    across a clock change, and "every month" from the 31st runs on the last
    day of shorter months.

    ``from_`` left out is the moment the schedule first ran (see
    :class:`StatefulTriggerInterface`); ``until`` is exclusive.
    """

    __slots__ = ("_description", "_from", "_interval_us", "_step", "_until")

    def __init__(
        self,
        interval: float | str | timedelta,
        from_: datetime | str | None = None,
        until: datetime | str = FAR_FUTURE,
    ) -> None:
        """Run every ``interval`` from ``from_`` until ``until``.

        Raises:
            InvalidArgumentError: If the interval is not positive or cannot be
                read, or a date has no timezone.
        """
        self._from = None if from_ is None else aware(from_, "start date")
        self._until = aware(until, "end date")
        self._interval_us = 0
        self._step: _CalendarStep | None = None
        # The bounds given are part of what the trigger is: two windows of one
        # interval are two triggers, and describe themselves apart.
        bounds = "" if self._from is None else f" from {self._from.isoformat()}"
        if until is not FAR_FUTURE:
            bounds += f" until {self._until.isoformat()}"
        self._description = self._read(interval) + bounds

    @override
    def __str__(self) -> str:
        return self._description

    @override
    def continue_(self, started_at: datetime, /) -> None:
        if self._from is None:
            self._from = aware(started_at, "start date")

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        run = aware(run, "run date")
        if self._from is None:
            self._from = run
        if self._step is not None:
            return self._next_on_calendar(self._from, self._step, run)
        # Every comparison is between absolute instants: two dates on one zone
        # compare by their wall clock, which ignores fold, so the hour a clock
        # goes back — lived through twice — would otherwise collapse to one.
        until_at = microseconds(self._until)
        run_at = microseconds(run)
        if until_at <= run_at:
            return None
        start = microseconds(self._from)
        passed = (run_at - start) // self._interval_us
        next_run = from_microseconds((passed + 1) * self._interval_us + start, self._from.tzinfo)
        if start > microseconds(next_run):
            return self._from if until_at > start else None
        return next_run if until_at > microseconds(next_run) else None

    def _next_on_calendar(
        self, start: datetime, step: _CalendarStep, run: datetime
    ) -> datetime | None:
        count = _steps_before(start, step, run)
        until_at = microseconds(self._until)
        run_at = microseconds(run)
        while True:
            candidate = _shift(start, step.months * count, step.days * count)
            candidate_at = microseconds(candidate)
            if candidate_at >= until_at:
                return None
            if candidate_at > run_at:
                return candidate
            count += 1

    def _read(self, interval: float | str | timedelta) -> str:
        """Set the interval from ``interval`` and return the trigger's description.

        Raises:
            InvalidArgumentError: If it is not positive or cannot be read.
        """
        if isinstance(interval, bool):
            raise InvalidArgumentError(f'Invalid interval "{interval}".')
        if isinstance(interval, str) and interval.isdigit():
            interval = int(interval)
        if isinstance(interval, (int, float)):
            # Rounded to the microsecond, as a timedelta is: 1.5 is a second and a half.
            self._interval_us = _positive(round(interval * _MICROSECONDS_PER_SECOND))
            return f"every {_seconds(self._interval_us)} seconds"
        if isinstance(interval, timedelta):
            self._interval_us = _positive(interval // timedelta(microseconds=1))
            return f"every {_seconds(self._interval_us)} seconds"
        if interval.startswith("P"):
            self._interval_us = _positive(_iso_duration_us(interval))
            return f"every {self._interval_us // _MICROSECONDS_PER_SECOND} seconds ({interval})"
        matched = _RELATIVE.match(interval)
        if matched is None:
            raise InvalidArgumentError(f'Invalid interval "{interval}".')
        amount, unit = int(matched.group(1)), matched.group(2).lower()
        if unit in _SECONDS_PER_UNIT:
            self._interval_us = _positive(
                amount * _SECONDS_PER_UNIT[unit] * _MICROSECONDS_PER_SECOND
            )
        else:
            _ = _positive(amount)
            self._step = _CalendarStep(
                months=amount * _MONTHS_PER_UNIT.get(unit, 0),
                days=amount * _DAYS_PER_UNIT.get(unit, 0),
            )
        return f"every {interval}"


def _positive(value: int) -> int:
    if value <= 0:
        raise InvalidArgumentError('The "interval" argument must be greater than zero.')
    return value


def _seconds(value_us: int) -> str:
    whole, fraction = divmod(value_us, _MICROSECONDS_PER_SECOND)
    return str(whole) if fraction == 0 else str(value_us / _MICROSECONDS_PER_SECOND)


def _iso_duration_us(duration: str) -> int:
    """Return an ISO 8601 duration in microseconds, measured from the epoch.

    Years and months have no fixed length, so they are measured the way the
    epoch's calendar lays them out — ``P1M`` is January 1970's 31 days.

    Raises:
        InvalidArgumentError: If ``duration`` is not an ISO 8601 duration.
    """
    matched = _ISO_DURATION.match(duration)
    if matched is None:
        raise InvalidArgumentError(f'Invalid interval "{duration}".')
    years, months, weeks, days, hours, minutes, seconds = (int(g or 0) for g in matched.groups())
    end = _shift(EPOCH, years * 12 + months, weeks * 7 + days) + timedelta(
        hours=hours, minutes=minutes, seconds=seconds
    )
    return microseconds(end)


def _steps_before(start: datetime, step: _CalendarStep, run: datetime) -> int:
    """Return a number of steps from ``start`` that stays at or before ``run``.

    Where the search for the next run begins, so a schedule started long ago
    does not walk every step since. One step of slack covers month ends and
    clock changes.
    """
    if step.months:
        elapsed = (run.year - start.year) * 12 + run.month - start.month
        return max(0, elapsed // step.months - 1)
    return max(0, (run - start).days // step.days - 1)


def _shift(start: datetime, months: int, days: int) -> datetime:
    """Move ``start`` by whole months, then whole days, on its own wall clock.

    A month landing past the end of a shorter one lands on its last day, and
    a wall clock the zone skipped over is shown on the hour that replaced it.
    """
    return shift_calendar(start, months=months, days=days)
