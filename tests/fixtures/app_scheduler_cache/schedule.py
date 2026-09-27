"""A stateful schedule on the ``scheduler`` pool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from typing_extensions import override
from xtr_cache_contracts import CacheInterface
from xtr_dependency_injection import Target
from xtr_messenger import as_message_handler

from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule


@dataclass(frozen=True)
class Beat:
    """The schedule's message."""


@as_message_handler(Beat)
async def beat(message: Beat) -> None:
    """Accept every beat."""
    del message


@as_schedule("default")
class StatefulSchedule(ScheduleProviderInterface):
    """Keeps how far it got in the pool the scheduler bundle adds."""

    def __init__(self, cache: Annotated[CacheInterface, Target("scheduler")]) -> None:
        """Build the schedule, stateful in ``cache``."""
        self._schedule: Schedule = Schedule(RecurringMessage.every(60, Beat())).stateful(cache)

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule
