"""End-to-end: declared schedules and tasks, run by a kernel's messenger worker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from xtr_clock import Clock, MockClock
from xtr_console import Application, CommandTester
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test
from xtr_messenger import InMemoryTransport, MessageBusConfig, TransportFactory, WorkerFactory

from tests.fixtures.app_scheduler.services import Journal
from tests.fixtures.app_scheduler_override.schedule import HANDLED, Tock
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from xtr_dependency_injection import BootedKernel

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


async def booted_at_start() -> AbstractAsyncContextManager[BootedKernel]:
    """Boot the fixture application on a clock frozen at the start of 2026."""
    kernel = Kernel("tests.fixtures.app_scheduler", env="test")
    return await boot_for_test(kernel, overrides={Clock: Clock(MockClock(START))})


async def test_the_schedule_and_its_tasks_run_on_scheduler_default() -> None:
    async with await booted_at_start() as booted:
        workers = await booted.container.get(WorkerFactory)

        await asyncio.wait_for(workers.worker(["scheduler_default"]).run(), 5)

        journal = await booted.container.get(Journal)

    assert sorted(set(journal.entries)) == ["cleanup", "ping eu", "tick"]
    assert journal.results[0] == "ticked"


async def test_debug_scheduler_lists_the_schedule_with_its_tasks() -> None:
    async with await booted_at_start() as booted:
        application = await booted.container.get(Application)
        tester = CommandTester(application, "debug:scheduler", width=250)

        _ = await tester.execute()

    display = tester.display
    assert "Tick" in display
    assert "@tests.fixtures.app_scheduler.services.Cleanup::run" in display
    assert "@tests.fixtures.app_scheduler.services.ping" in display
    assert "ProductionOnly" not in display


async def test_an_application_s_own_scheduler_transport_wins() -> None:
    HANDLED.clear()
    kernel = Kernel("tests.fixtures.app_scheduler_override", env="test")
    async with await boot_for_test(kernel, overrides={Clock: Clock(MockClock(START))}) as booted:
        workers = await booted.container.get(WorkerFactory)
        config = await booted.container.get(MessageBusConfig)

        await asyncio.wait_for(workers.worker(["scheduler_default"]).run(), 5)

        transports = await booted.container.get(TransportFactory)
        tocks = transports.create({"tocks": config.transports["tocks"]})["tocks"]

    assert HANDLED == ["RedispatchMessage"]
    assert isinstance(tocks, InMemoryTransport)
    assert tocks.messages == (Tock(),)


async def test_a_schedule_whose_tasks_are_all_elsewhere_is_still_consumable() -> None:
    kernel = Kernel("tests.fixtures.app_scheduler_prod_only", env="test")
    async with await boot_for_test(kernel, overrides={Clock: Clock(MockClock(START))}) as booted:
        workers = await booted.container.get(WorkerFactory)
        schedules = await booted.container.get(ScheduleProviderLocator)

        worker = workers.worker(["scheduler_nightly"])
        running = asyncio.create_task(worker.run())
        await asyncio.sleep(0)
        worker.stop()
        await asyncio.wait_for(running, 1)

        nightly = (await schedules.get("nightly")).get_schedule()

    assert nightly.recurring_messages == ()
