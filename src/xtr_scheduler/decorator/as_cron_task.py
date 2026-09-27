"""Declare a task run on a cron expression."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_scheduler.registry.task_declaration import TaskDeclaration

from ._task_decorator import TargetT, declaring, names

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = ["as_cron_task"]


def as_cron_task(  # noqa: PLR0913 — one keyword per thing a task can declare
    expression: str,
    *,
    timezone: str | None = None,
    jitter: int | None = None,
    arguments: Iterable[object] | None = None,
    schedule: str = "default",
    method: str | None = None,
    transports: str | Iterable[str] | None = None,
    env: str | Iterable[str] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Run the decorated class, method or function whenever ``expression`` matches.

    For example::

        @as_cron_task("0 3 * * *", timezone="Europe/Bucharest")
        async def purge_expired_sessions() -> None: ...


        @as_cron_task("#daily", arguments=["eu"], method="build")
        class Reports:
            def __init__(self, repository: ReportRepository) -> None: ...

            async def build(self, region: str) -> None: ...

    A class is called through ``method`` — itself, with ``__call__``, when
    none is given. Decorating a method in a class body calls that method.
    Repeat the decorator for several runs of one target.

    Args:
        expression: A cron expression; hashed ones pick their values per task.
        timezone: The zone the expression is read in; the clock's when ``None``.
        jitter: Delay each run at random by up to this many seconds.
        arguments: Positional arguments of each call, JSON values.
        schedule: The schedule the task joins.
        method: The method of a class to call.
        transports: Send each run to these transports, to be handled where
            they are consumed, rather than where the schedule is.
        env: Only in these environments; every environment when ``None``.
    """
    return declaring(
        TaskDeclaration(
            kind="cron",
            expression=expression,
            timezone=timezone,
            jitter=jitter,
            arguments=tuple(arguments) if arguments is not None else (),
            schedule=schedule,
            method=method,
            transports=names(transports),
            env=names(env),
        )
    )
