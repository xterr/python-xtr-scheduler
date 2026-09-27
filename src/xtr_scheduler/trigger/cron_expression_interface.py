"""A cron expression, read by whichever library the scheduler is given."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from datetime import datetime, tzinfo

__all__ = ["CronExpressionInterface"]


@runtime_checkable
class CronExpressionInterface(Protocol):
    """A parsed cron expression that can say when it next matches.

    The scheduler depends on this and never on a cron library, so the library
    can be replaced without touching a trigger — only an implementation of
    this, beside the others under ``bridge/``.
    """

    def next_after(self, run: datetime, timezone: tzinfo, /) -> datetime:
        """Return the first match strictly after ``run``, read on the clock of ``timezone``."""
        ...

    @override
    def __str__(self) -> str:
        """Return the expression, as written."""
        ...
