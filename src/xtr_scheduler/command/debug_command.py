"""``debug:scheduler``: what each schedule runs, and when it runs next."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, ClassVar, Final, final

from xtr_cache_contracts import CacheItemPoolInterface
from xtr_clock import DatePoint, now
from xtr_clock.exception import ClockError
from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape

from xtr_scheduler._time import add_months
from xtr_scheduler.recurring_message import RecurringMessage
from xtr_scheduler.schedule import Schedule
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

__all__ = ["DebugCommand"]

#: Stands for "no schedules given": ``use_schedules()`` or the declared ones are used.
_UNSET: Final = ScheduleProviderLocator({})

_Row = tuple[str, str, datetime | None]


@as_command("debug:scheduler")
@final
class DebugCommand:
    """Lists schedules and their recurring messages, with when each runs next.

    A container builds it with the schedules its bundle wired; without one it
    reads those given to :meth:`use_schedules`, or else the ones declared in
    this process.
    """

    __slots__ = ("_schedules",)

    _process_schedules: ClassVar[ScheduleProviderLocator | None] = None

    def __init__(self, schedules: ScheduleProviderLocator = _UNSET) -> None:
        """List ``schedules``, or those set with :meth:`use_schedules` when omitted."""
        self._schedules = schedules

    @classmethod
    def use_schedules(cls, schedules: ScheduleProviderLocator | None) -> None:
        """List ``schedules`` wherever no container supplies any."""
        cls._process_schedules = schedules

    async def __call__(
        self,
        io: ConsoleStyle,
        *schedule: str,
        date: str | None = None,
        show_all: Annotated[bool, Option(name="all")] = False,
        sort: bool = False,
    ) -> int:
        """List schedules and their recurring messages.

        With no schedule named, every one is listed. A stateful schedule's next
        runs are computed from where its saved state says it got to, unless a
        date is given.

        Args:
            io: Where the command writes.
            schedule: The schedules to list; every one when none is named.
            date: Compute next runs from this date — ISO 8601, or a modifier
                such as ``+1 day`` — instead of now.
            show_all: Also list recurring messages that will never run again.
            sort: Sort each schedule's messages by their next run; those that
                never run again come first.
        """
        io.title("Scheduler")
        schedules = self._resolved()
        names = schedule or schedules.names()
        if not names:
            io.error("No schedules found.")
            return ExitCode.INVALID
        try:
            reference = now(date) if date is not None else now()
        except ClockError as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        if date is not None:
            io.text(f"All next run dates computed from {reference.isoformat()}.")
        for name in names:
            io.section(escape(name))
            if not schedules.has(name):
                io.error(f'The schedule "{escape(name)}" is not found.')
                return ExitCode.FAILURE
            listed = (await schedules.get(name)).get_schedule()
            await self._list(
                io, name, listed, reference, explicit=date is not None, show_all=show_all, sort=sort
            )
        return ExitCode.SUCCESS

    async def _list(  # noqa: PLR0913 — one keyword per option of the command
        self,
        io: ConsoleStyle,
        name: str,
        schedule: Schedule,
        reference: DatePoint,
        *,
        explicit: bool,
        show_all: bool,
        sort: bool,
    ) -> None:
        messages = schedule.recurring_messages
        if not messages:
            io.warning(f'No recurring messages found for schedule "{escape(name)}".')
            return
        base: datetime = reference
        saved = None if explicit else await _checkpoint_time(schedule, name)
        if saved is not None:
            base = saved
            io.text(
                f'Schedule "{escape(name)}" is stateful: next run dates computed from stored '
                f"checkpoint {saved.isoformat()}."
            )
        rows = [row for row in (_row(message, base) for message in messages) if show_all or row[2]]
        if sort:
            rows.sort(key=lambda row: (row[2] is not None, row[2] or reference))
        io.table(
            ["Trigger", "Provider", "Next Run On", "Next Run In"],
            [
                [
                    escape(trigger),
                    escape(provider),
                    next_run.isoformat() if next_run is not None else "-",
                    format_interval(reference, next_run) if next_run is not None else "-",
                ]
                for trigger, provider, next_run in rows
            ],
        )

    def _resolved(self) -> ScheduleProviderLocator:
        if self._schedules is not _UNSET:
            return self._schedules
        if self._process_schedules is not None:
            return self._process_schedules
        from xtr_scheduler.registry.declared_schedules import (  # noqa: PLC0415 — declarations are read when first needed
            declared_schedules,
        )

        return declared_schedules()


def _row(message: RecurringMessage, base: datetime) -> _Row:
    trigger = message.get_trigger()
    return (str(trigger), str(message.get_provider()), trigger.get_next_run_date(base))


async def _checkpoint_time(schedule: Schedule, name: str) -> datetime | None:
    """Return where a stateful schedule got to, read without writing anything.

    Best effort: a pool that cannot be read item by item, or holds something
    unexpected, leaves the listing computed from now.
    """
    state = schedule.get_state()
    if not isinstance(state, CacheItemPoolInterface):
        return None
    item = await state.get_item(f"scheduler_checkpoint_{name}")
    if not item.is_hit():
        return None
    saved = item.get()
    if isinstance(saved, (tuple, list)) and saved and isinstance(saved[0], datetime):
        return saved[0]
    return None


def format_interval(start: datetime, end: datetime) -> str:
    """Describe how long from ``start`` to ``end`` — ``-`` first when ``end`` is past.

    In years, months, days, hours and minutes, then seconds to the
    millisecond, leaving out what is zero.
    """
    overdue = end < start
    first, last = (end, start) if overdue else (start, end)
    first, last = first.astimezone(UTC), last.astimezone(UTC)
    months = (last.year - first.year) * 12 + last.month - first.month
    if add_months(first, months) > last:
        months -= 1
    rest = last - add_months(first, months)
    hours, remainder = divmod(rest.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = [
        f"{value} {unit}"
        for value, unit in (
            (months // 12, "y"),
            (months % 12, "mo"),
            (rest.days, "d"),
            (hours, "h"),
            (minutes, "min"),
        )
        if value
    ]
    fraction = round(seconds + rest.microseconds / 1_000_000, 3)
    if fraction:
        parts.append(f"{fraction:.3f}".rstrip("0").rstrip(".") + " s")
    described = ", ".join(parts) or "0 s"
    return f"-{described}" if overdue else described
