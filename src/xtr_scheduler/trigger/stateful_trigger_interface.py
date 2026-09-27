"""A trigger anchored to when its schedule first ran."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .trigger_interface import TriggerInterface

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["StatefulTriggerInterface"]


@runtime_checkable
class StatefulTriggerInterface(TriggerInterface, Protocol):
    """A trigger whose runs are counted from a starting point.

    "Every hour" needs to know an hour after *what*. Told nothing, it would
    count from whenever the process started, and a restart would shift every
    run. The scheduler calls :meth:`continue_` with the moment the schedule
    first ran — kept across restarts when the schedule is stateful — so the
    runs stay where they were.
    """

    def continue_(self, started_at: datetime, /) -> None:
        """Count from ``started_at``, unless a starting point was given explicitly."""
        ...
