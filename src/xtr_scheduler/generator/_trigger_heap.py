"""The recurring messages of a schedule, earliest next run first."""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_scheduler.recurring_message import RecurringMessage

__all__ = ["TriggerHeap"]


@final
class TriggerHeap:
    """A min-heap of ``(next run, position, recurring message)``.

    Ordered by time, then by position in the schedule, so messages due at the
    same time come out in the order they were added — and two entries never
    compare their messages, since no two share a position.
    """

    __slots__ = ("_entries", "time")

    def __init__(self, time: datetime) -> None:
        """Start empty; ``time`` is the moment the heap was built for."""
        self.time = time
        self._entries: list[tuple[datetime, int, RecurringMessage]] = []

    def __bool__(self) -> bool:
        """Tell whether anything is left."""
        return bool(self._entries)

    def top(self) -> tuple[datetime, int, RecurringMessage]:
        """Return the earliest entry without removing it."""
        return self._entries[0]

    def insert(self, time: datetime, index: int, message: RecurringMessage) -> None:
        """Add ``message``, next due at ``time``, at position ``index``."""
        heapq.heappush(self._entries, (time, index, message))

    def extract(self) -> tuple[datetime, int, RecurringMessage]:
        """Remove and return the earliest entry."""
        return heapq.heappop(self._entries)
