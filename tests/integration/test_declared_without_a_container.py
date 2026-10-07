"""End-to-end with no container: the caller wires the handler from the declarations itself."""

from __future__ import annotations

import asyncio
from typing import final

import pytest
from xtr_clock.testing import mock_time
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import (
    HandlersLocator,
    MessageBusConfig,
    TransportConfig,
    WorkerFactory,
)
from xtr_messenger.event import WorkerRunningEvent

from xtr_scheduler.decorator import as_periodic_task
from xtr_scheduler.messenger import ServiceCallMessage, ServiceCallMessageHandler, TaskMethods
from xtr_scheduler.registry import declared_task_methods, declared_task_targets

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


async def test_declared_tasks_run_when_the_caller_wires_the_handler() -> None:
    RAN.clear()
    config = MessageBusConfig(
        transports={"scheduler": TransportConfig("schedule://tests-no-container")}
    )
    events = EventDispatcher()
    events.add_listener(WorkerRunningEvent, StopAfter(3))
    # No container builds the handler, so the caller supplies its dependencies:
    # the declared targets and the declared method allow-list.
    handler = ServiceCallMessageHandler(
        declared_task_targets(), TaskMethods(declared_task_methods())
    )
    handlers = HandlersLocator()
    _ = handlers.register(ServiceCallMessage, handler)

    with mock_time("2026-01-01T00:00:00+00:00") as clock:
        worker = WorkerFactory(config, handlers=handlers, event_dispatcher=events).worker(
            ["scheduler"]
        )
        await asyncio.wait_for(worker.run(), 5)

        assert RAN == ["report eu", "refresh", "report eu"]
        assert clock.now().isoformat() == "2026-01-01T00:02:00+00:00"
