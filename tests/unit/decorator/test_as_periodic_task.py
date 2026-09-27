"""Declare a task run at a fixed interval."""

from __future__ import annotations

from datetime import timedelta

from xtr_scheduler.decorator import as_periodic_task
from xtr_scheduler.registry import TaskDeclaration, tasks_declared_on


@as_periodic_task(
    timedelta(minutes=10),
    from_="2026-01-01T00:00:00+00:00",
    until="2027-01-01T00:00:00+00:00",
    method="refresh",
    schedule="tests-periodic",
)
class Rates:
    """A task class calling a method."""

    async def refresh(self) -> None: ...


def test_the_interval_and_its_bounds_are_recorded() -> None:
    assert tasks_declared_on(Rates) == (
        TaskDeclaration(
            kind="every",
            frequency=timedelta(minutes=10),
            from_="2026-01-01T00:00:00+00:00",
            until="2027-01-01T00:00:00+00:00",
            method="refresh",
            schedule="tests-periodic",
        ),
    )
