"""The scheduler bundle honours the zero-config contract."""

from __future__ import annotations

import pytest
from xtr_cache.bundle import CacheConfig, PoolConfig
from xtr_dependency_injection.testing import assert_zero_config

from xtr_scheduler.bundle import SCHEDULER_POOL, SchedulerBundle
from xtr_scheduler.bundle.scheduler_bundle import _add_scheduler_pool

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(SchedulerBundle)


def test_the_scheduler_pool_is_added_on_the_app_pool_s_adapter() -> None:
    config = _add_scheduler_pool(CacheConfig(app="array", pools={"sessions": "array"}))

    assert isinstance(config, CacheConfig)
    assert config.pools[SCHEDULER_POOL] == PoolConfig()
    assert config.pool_configs()[SCHEDULER_POOL].adapter == ("array",)
    assert "sessions" in config.pools


def test_a_scheduler_pool_the_application_configured_is_left_alone() -> None:
    own = PoolConfig(adapter="redis://cache:6379/2")
    config = CacheConfig(pools={SCHEDULER_POOL: own})

    assert _add_scheduler_pool(config) is config
