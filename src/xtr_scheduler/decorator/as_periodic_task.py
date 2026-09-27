"""Declare a task run at a fixed interval."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_scheduler.registry.task_declaration import TaskDeclaration

from ._task_decorator import TargetT, declaring, names

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import datetime, timedelta

__all__ = ["as_periodic_task"]


def as_periodic_task(  # noqa: PLR0913 — one keyword per thing a task can declare
    frequency: float | str | timedelta,
    *,
    from_: datetime | str | None = None,
    until: datetime | str | None = None,
    jitter: int | None = None,
    arguments: Iterable[object] | None = None,
    schedule: str = "default",
    method: str | None = None,
    transports: str | Iterable[str] | None = None,
    env: str | Iterable[str] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Run the decorated class, method or function every ``frequency``.

    For example::

        @as_periodic_task("10 minutes", jitter=30)
        async def refresh_rates() -> None: ...

    ``frequency`` takes every form
    :class:`~xtr_scheduler.trigger.PeriodicalTrigger` does. Runs are counted
    from ``from_`` — from when the schedule first ran, when ``None`` — until
    ``until``. The other arguments mean what they do for
    :func:`~xtr_scheduler.decorator.as_cron_task`.
    """
    return declaring(
        TaskDeclaration(
            kind="every",
            frequency=frequency,
            from_=from_,
            until=until,
            jitter=jitter,
            arguments=tuple(arguments) if arguments is not None else (),
            schedule=schedule,
            method=method,
            transports=names(transports),
            env=names(env),
        )
    )
