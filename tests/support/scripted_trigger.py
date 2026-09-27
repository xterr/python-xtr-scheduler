"""A trigger that runs at fixed times, and checks it is asked sensibly."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import final

from typing_extensions import override

from xtr_scheduler.trigger import TriggerInterface


def moment(time: str) -> datetime:
    """Return ``time`` of day on the fixed test date, in UTC."""
    return datetime.fromisoformat(f"2020-02-20T{time}").replace(tzinfo=UTC)


@final
class ScriptedTrigger(TriggerInterface):
    """Runs at each of ``runs``, and fails the test when asked out of order.

    Asked about a date earlier than the last, or about the same date more
    than twice, the generator is recomputing what it should already know —
    the reference suite catches exactly that, and so does this.
    """

    def __init__(self, *runs: str) -> None:
        self._runs = sorted(moment(run) for run in runs)
        self._last = datetime.min.replace(tzinfo=UTC)
        self._count = 0

    @override
    def __str__(self) -> str:
        return ""

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        if run > self._last:
            self._last, self._count = run, 1
        elif run == self._last and self._count < 2:
            self._count += 1
        else:
            raise AssertionError(f"invalid tick {run.isoformat()}")
        for scheduled in self._runs:
            if run < scheduled:
                return scheduled
        raise AssertionError(f"there is no next run for tick {run.isoformat()}")
