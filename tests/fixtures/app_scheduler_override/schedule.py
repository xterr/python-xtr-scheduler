"""The schedule, and what stops the worker."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override
from xtr_event_dispatcher import as_event_listener
from xtr_messenger.event import WorkerMessageHandledEvent, WorkerRunningEvent

from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule

#: What the worker handled, by message type — shared with the test.
HANDLED: list[str] = []


@dataclass(frozen=True)
class Tock:
    """The schedule's message; routed, never handled here."""


@as_schedule("default")
class DefaultSchedule(ScheduleProviderInterface):
    """A schedule of one message a minute."""

    def __init__(self) -> None:
        """Build the schedule."""
        self._schedule: Schedule = Schedule(RecurringMessage.every(60, Tock()))

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule


@as_event_listener()
def record(event: WorkerMessageHandledEvent) -> None:
    """Write down the type of what the worker handled."""
    HANDLED.append(type(event.envelope.message).__name__)


@as_event_listener()
def stop_after_one(event: WorkerRunningEvent) -> None:
    """Stop the worker after its first message."""
    event.worker.stop()
