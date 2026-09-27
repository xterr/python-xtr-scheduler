"""A schedule provider whose schedule also runs declared tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_scheduler.recurring_message import RecurringMessage
    from xtr_scheduler.schedule import Schedule

__all__ = ["ScheduleWithTasks"]


@final
class ScheduleWithTasks(ScheduleProviderInterface):
    """Hands over ``inner``'s schedule with ``tasks`` added to it — once.

    What a schedule declared with ``@as_schedule`` becomes when tasks are
    declared on the same schedule: the provider builds the schedule as it
    likes, and the tasks join it.
    """

    __slots__ = ("_inner", "_schedule", "_tasks")

    def __init__(self, inner: ScheduleProviderInterface, tasks: Sequence[RecurringMessage]) -> None:
        """Add ``tasks`` to the schedule ``inner`` hands over."""
        self._inner = inner
        self._tasks = tuple(tasks)
        self._schedule: Schedule | None = None

    @property
    def inner(self) -> ScheduleProviderInterface:
        """Return the provider whose schedule the tasks join."""
        return self._inner

    @override
    def get_schedule(self) -> Schedule:
        if self._schedule is None:
            self._schedule = self._inner.get_schedule().add(*self._tasks)
        return self._schedule
