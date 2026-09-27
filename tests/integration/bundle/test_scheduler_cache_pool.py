"""With the cache bundle, schedules get a ``scheduler`` pool of their own."""

from __future__ import annotations

from contextlib import aclosing

import pytest
from xtr_cache_contracts import CacheInterface, CacheItemPoolInterface
from xtr_clock import Clock, MockClock
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from xtr_scheduler.bundle import SCHEDULER_POOL
from xtr_scheduler.generator import MessageGenerator
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


async def test_a_schedule_keeps_its_state_in_the_scheduler_pool_apart_from_the_app_s() -> None:
    kernel = Kernel("tests.fixtures.app_scheduler_cache", env="test")
    async with await boot_for_test(kernel, overrides={Clock: Clock(MockClock(START))}) as booted:
        container = booted.container
        schedules = await container.get(ScheduleProviderLocator)
        generator = MessageGenerator(await schedules.get("default"), "default")

        async with aclosing(generator.get_messages()) as due:
            _ = [pair async for pair in due]

        pool = await container.get(CacheInterface, SCHEDULER_POOL)
        app = await container.get(CacheItemPoolInterface)
        assert isinstance(pool, CacheItemPoolInterface)
        assert (await pool.get_item("scheduler_checkpoint_default")).is_hit()
        assert not (await app.get_item("scheduler_checkpoint_default")).is_hit()


async def test_without_the_cache_bundle_there_is_no_pool() -> None:
    kernel = Kernel("tests.fixtures.app_scheduler", env="test")
    async with await boot_for_test(kernel, overrides={Clock: Clock(MockClock(START))}) as booted:
        assert not booted.container.has(CacheInterface, SCHEDULER_POOL)
