"""What the scheduled work writes to, the schedule, and its tasks."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override
from xtr_dependency_injection import Injected, as_service
from xtr_messenger import as_message_handler

from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_cron_task, as_periodic_task, as_schedule
from xtr_scheduler.event import PostRunEvent


@as_service
class Journal:
    """What ran, in order."""

    def __init__(self) -> None:
        """Start empty."""
        self.entries: list[str] = []
        self.results: list[object] = []


@dataclass(frozen=True)
class Tick:
    """The schedule's own message."""

    number: int = 0


@as_message_handler(Tick)
class TickHandler:
    """Writes each tick down."""

    def __init__(self, journal: Journal) -> None:
        """Write into ``journal``."""
        self._journal: Journal = journal

    async def __call__(self, message: Tick) -> str:
        """Record the tick."""
        del message
        self._journal.entries.append("tick")
        return "ticked"


@as_schedule("default")
class DefaultSchedule(ScheduleProviderInterface):
    """The default schedule, built with a service of the application."""

    def __init__(self, journal: Journal) -> None:
        """Build the schedule, reporting every run's result to ``journal``."""

        def report(event: PostRunEvent) -> None:
            journal.results.append(event.result)

        self._schedule: Schedule = Schedule(RecurringMessage.every(60, Tick())).after(report)

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule


@as_periodic_task(60, method="run")
class Cleanup:
    """A task class with a dependency, joining the default schedule."""

    def __init__(self, journal: Journal) -> None:
        """Write into ``journal``."""
        self._journal: Journal = journal

    def run(self) -> str:
        """Record the cleanup."""
        self._journal.entries.append("cleanup")
        return "cleaned"


@as_periodic_task(60, env="prod")
class ProductionOnly:
    """A task left out of every environment but production."""

    def __call__(self) -> None:
        """Never runs in the tests."""


@as_cron_task("* * * * *", arguments=["eu"])
async def ping(region: str, journal: Injected[Journal]) -> None:
    """A function task, with its argument and a service."""
    journal.entries.append(f"ping {region}")
