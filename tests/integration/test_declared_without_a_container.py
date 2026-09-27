"""End-to-end with no container: discovery finds the transport, declarations fill it."""

from __future__ import annotations

import asyncio
from typing import final

import pytest
from xtr_clock.testing import mock_time
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import MessageBusConfig, TransportConfig, WorkerFactory
from xtr_messenger.event import WorkerRunningEvent

from xtr_scheduler.decorator import as_periodic_task

pytestmark = pytest.mark.anyio

RAN: list[str] = []


@as_periodic_task(60, schedule="tests-no-container", arguments=["eu"], method="build")
class Report:
    """A task class built with no arguments."""

    def build(self, region: str) -> None:
        RAN.append(f"report {region}")


@as_periodic_task(90, schedule="tests-no-container")
async def refresh() -> None:
    RAN.append("refresh")


@final
class StopAfter:
    """Stops the worker once ``count`` tasks have run."""

    def __init__(self, count: int) -> None:
        self._count = count

    def __call__(self, event: WorkerRunningEvent) -> None:
        if len(RAN) >= self._count:
            event.worker.stop()


async def test_declared_tasks_run_on_a_discovered_schedule_transport() -> None:
    RAN.clear()
    config = MessageBusConfig(
        transports={"scheduler": TransportConfig("schedule://tests-no-container")}
    )
    events = EventDispatcher()
    events.add_listener(WorkerRunningEvent, StopAfter(3))

    with mock_time("2026-01-01T00:00:00+00:00") as clock:
        worker = WorkerFactory(config, event_dispatcher=events).worker(["scheduler"])
        await asyncio.wait_for(worker.run(), 5)

        assert RAN == ["report eu", "refresh", "report eu"]
        assert clock.now().isoformat() == "2026-01-01T00:02:00+00:00"
