"""A messenger worker consuming a schedule, end to end."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, final

import pytest
from xtr_clock import MockClock
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import (
    HandlersLocator,
    InMemoryTransport,
    InMemoryTransportFactory,
    MessageBusConfig,
    RedispatchMessage,
    TransportConfig,
    WorkerFactory,
    WorkerInterface,
)
from xtr_messenger.event import WorkerMessageHandledEvent

from tests.support.messages import Named
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.event_listener import DispatchSchedulerEventListener
from xtr_scheduler.messenger import ScheduledStamp, SchedulerTransportFactory
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from xtr_scheduler.event import PostRunEvent

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"
_TIMEOUT = 5.0


@final
class StopAfter:
    """Stops the worker once it has handled ``count`` messages."""

    def __init__(self, count: int) -> None:
        self.worker: WorkerInterface | None = None
        self._left = count

    def __call__(self, event: WorkerMessageHandledEvent) -> None:
        del event
        self._left -= 1
        if self._left == 0 and self.worker is not None:
            self.worker.stop()


async def test_a_redispatched_run_lands_where_routing_sends_it() -> None:
    clock = MockClock(START)
    schedule = Schedule(RecurringMessage.every(60, RedispatchMessage(Named("report"))))
    ran: list[PostRunEvent] = []
    _ = schedule.after(ran.append)
    in_memory = InMemoryTransportFactory()
    config = MessageBusConfig(
        transports={
            "scheduler_default": TransportConfig("schedule://default"),
            "reports": TransportConfig("in-memory://"),
        },
        routing={Named: "reports"},
    )
    events = EventDispatcher()
    stop = StopAfter(2)
    events.add_listener(WorkerMessageHandledEvent, stop)
    events.add_subscriber(
        DispatchSchedulerEventListener(ScheduleProviderLocator({"default": schedule}), events)
    )
    factories = [SchedulerTransportFactory({"default": schedule}, clock=clock), in_memory]
    workers = WorkerFactory(config, factories, HandlersLocator(), event_dispatcher=events)
    worker = workers.worker(["scheduler_default"])
    stop.worker = worker

    await asyncio.wait_for(worker.run(), _TIMEOUT)

    reports = in_memory.create(config.transports)["reports"]
    assert isinstance(reports, InMemoryTransport)
    assert reports.messages == (Named("report"), Named("report"))
    stamps = [envelope.last(ScheduledStamp) for envelope in reports.sent]
    assert [stamp.triggered_at.isoformat() for stamp in stamps if stamp is not None] == [
        "2026-01-01T00:01:00+00:00",
        "2026-01-01T00:02:00+00:00",
    ]
    assert [event.message for event in ran] == [Named("report"), Named("report")]


async def test_stopping_the_worker_ends_the_wait_for_the_next_run() -> None:
    schedule = Schedule(RecurringMessage.every(3600, Named("hourly")))
    config = MessageBusConfig(
        transports={"scheduler_default": TransportConfig("schedule://default")}
    )
    worker = WorkerFactory(config, [SchedulerTransportFactory({"default": schedule})]).worker(
        ["scheduler_default"]
    )
    running = asyncio.create_task(worker.run())
    await asyncio.sleep(0.05)

    worker.stop()

    await asyncio.wait_for(running, 0.5)
