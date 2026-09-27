"""What hands over a schedule."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .schedule import Schedule

__all__ = ["ScheduleProviderInterface"]


@runtime_checkable
class ScheduleProviderInterface(Protocol):
    """Builds, or holds, a :class:`~xtr_scheduler.schedule.Schedule`.

    An application declares a class implementing this with
    :func:`~xtr_scheduler.decorator.as_schedule`; it builds its schedule from
    whatever it was constructed with. A :class:`Schedule` is one too, and
    hands over itself.
    """

    def get_schedule(self) -> Schedule:
        """Return the schedule — the same one on every call."""
        ...
