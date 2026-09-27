"""Where a schedule records how far it got."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["CheckpointInterface"]


@runtime_checkable
class CheckpointInterface(Protocol):
    """How far a schedule got, and whether this process may carry on with it.

    Three facts: when the schedule first ran (:meth:`from_`), the time of the
    last run sent (:meth:`time`), and — since several messages can be due at
    the same time — the position of the last one sent at that time
    (:meth:`index`), so a batch interrupted half-way resumes after what it
    already sent.
    """

    async def acquire(self, now: datetime, /) -> bool:
        """Claim the schedule for this process and load how far it got.

        Returns:
            ``False`` when another process holds it; nothing is sent then.
        """
        ...

    def from_(self) -> datetime:
        """Return when the schedule first ran."""
        ...

    def time(self) -> datetime:
        """Return the time of the last run sent."""
        ...

    def index(self) -> int:
        """Return the position of the last message sent at :meth:`time`; ``-1`` for none."""
        ...

    async def save(self, time: datetime, index: int, /) -> None:
        """Record that the message at ``index``, due at ``time``, was sent."""
        ...

    async def release(self, now: datetime, next_time: datetime | None, /) -> None:
        """Hand the schedule back until ``next_time`` — for good when there is none."""
        ...

    async def close(self) -> None:
        """Hand the schedule back for good, if this process holds it — it stops running it."""
        ...
