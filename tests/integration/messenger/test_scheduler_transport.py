"""A messenger worker consuming a schedule, end to end."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import (
    Dsn,
    HandlersLocator,
    InMemoryTransport,
    InMemoryTransportFactory,
    JsonSerializer,
    MessageBusConfig,
    RedispatchMessage,
    TransportConfig,
    TransportFactoryInterface,
    WorkerFactory,
    WorkerInterface,
)
from xtr_messenger.event import WorkerMessageFailedEvent, WorkerMessageHandledEvent
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.support.messages import Named
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.event_listener import DispatchSchedulerEventListener
from xtr_scheduler.generator import MessageGenerator
from xtr_scheduler.messenger import ScheduledStamp, SchedulerTransport, SchedulerTransportFactory
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_messenger import SenderInterface

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

    def __call__(self, event: WorkerMessageHandledEvent | WorkerMessageFailedEvent) -> None:
        del event
        self._left -= 1
        if self._left == 0 and self.worker is not None:
            self.worker.stop()


@final
class PatientSchedulerTransportFactory(TransportFactoryInterface):
    """Serves one schedule, asking for due runs once an hour of the clock.

    The transport never waits past the next due run, so a longer poll changes
    nothing about when a run is sent: it only spares a frozen clock thousands
    of one-second steps on the way to a run a day away.
    """

    def __init__(self, schedule: Schedule, clock: MockClock) -> None:
        self._schedule = schedule
        self._clock = clock

    @override
    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == "schedule"

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        return {
            name: SchedulerTransport(
                MessageGenerator(self._schedule, "default", self._clock),
                name=name,
                clock=self._clock,
                poll_interval=3600,
            )
            for name in group
        }


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
    # Announced where "reports" is consumed and the run really handled, not here.
    assert ran == []


async def test_nightly_runs_around_a_clock_change_cross_a_serializing_transport() -> None:
    clock = MockClock("2026-10-23T12:00:00+00:00")
    schedule = Schedule(
        RecurringMessage.cron(
            "0 3 * * *", RedispatchMessage(Named("purge")), timezone="Europe/Bucharest"
        )
    )
    in_memory = InMemoryTransportFactory(
        JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
    )
    config = MessageBusConfig(
        transports={
            "scheduler_default": TransportConfig("schedule://default"),
            "purges": TransportConfig("in-memory://?serialize=true"),
        },
        routing={Named: "purges"},
    )
    events = EventDispatcher()
    stop = StopAfter(3)
    events.add_listener(WorkerMessageHandledEvent, stop)
    events.add_listener(WorkerMessageFailedEvent, stop)
    factories = [PatientSchedulerTransportFactory(schedule, clock), in_memory]
    workers = WorkerFactory(config, factories, HandlersLocator(), event_dispatcher=events)
    worker = workers.worker(["scheduler_default"])
    stop.worker = worker

    await asyncio.wait_for(worker.run(), _TIMEOUT)

    purges = in_memory.create(config.transports)["purges"]
    assert isinstance(purges, InMemoryTransport)
    stamps = [envelope.last(ScheduledStamp) for envelope in purges.sent]
    assert [
        (stamp.triggered_at.isoformat(), stamp.triggered_at.fold)
        for stamp in stamps
        if stamp is not None
    ] == [
        ("2026-10-24T03:00:00+03:00", 0),
        ("2026-10-25T03:00:00+03:00", 0),
        ("2026-10-25T03:00:00+02:00", 1),
    ]


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
