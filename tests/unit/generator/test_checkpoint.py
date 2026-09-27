"""How far a schedule got, kept in memory and optionally in a cache, under an optional lock."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from xtr_cache.adapter import ArrayAdapter
from xtr_lock import InMemoryStore, Key, Lock, NoLock

from tests.support.dates import at
from tests.support.flaky_cache import FlakyCache
from tests.support.recording_lock import RecordingLock
from xtr_scheduler.exception import SchedulerRuntimeError
from xtr_scheduler.generator import Checkpoint

if TYPE_CHECKING:
    from xtr_cache_contracts import CacheInterface, ItemInterface

pytestmark = pytest.mark.anyio

NOW = at("2020-02-20T20:20:20+00:00")


async def stored(cache: CacheInterface, key: str) -> object:
    async def nothing(item: ItemInterface) -> object:
        del item
        return None

    return await cache.get(key, nothing)


async def put(cache: CacheInterface, key: str, value: object) -> None:
    async def fixed(item: ItemInterface) -> object:
        del item
        return value

    _ = await cache.get(key, fixed, beta=float("inf"))


def locked(resource: str, store: InMemoryStore | None = None) -> Lock:
    return Lock(Key(resource), store if store is not None else InMemoryStore())


async def test_without_a_lock_or_a_cache_it_remembers_in_memory() -> None:
    later = NOW + timedelta(hours=1)
    checkpoint = Checkpoint("dummy")

    assert await checkpoint.acquire(NOW)
    assert (checkpoint.time(), checkpoint.index()) == (NOW, -1)
    await checkpoint.save(later, 7)
    assert (checkpoint.time(), checkpoint.index()) == (later, 7)
    await checkpoint.release(later, None)


async def test_the_first_acquire_starts_the_saved_state() -> None:
    cache = ArrayAdapter()
    checkpoint = Checkpoint("cache", NoLock(), cache)

    assert await checkpoint.acquire(NOW)

    assert (checkpoint.time(), checkpoint.index()) == (NOW, -1)
    assert await stored(cache, "cache") == (NOW, -1, NOW)


async def test_acquiring_loads_the_saved_state_and_fills_a_missing_start() -> None:
    cache = ArrayAdapter()
    await put(cache, "cache", (NOW, 0))
    started = NOW + timedelta(minutes=1)
    checkpoint = Checkpoint("cache", NoLock(), cache)

    assert await checkpoint.acquire(started)

    assert (checkpoint.time(), checkpoint.index()) == (NOW, 0)
    assert await stored(cache, "cache") == (NOW, 0, started)


async def test_with_a_lock_the_first_acquire_takes_it() -> None:
    lock = locked("lock")
    checkpoint = Checkpoint("dummy", lock)

    assert await checkpoint.acquire(NOW)

    assert (checkpoint.time(), checkpoint.from_(), checkpoint.index()) == (NOW, NOW, -1)
    assert await lock.is_acquired()


async def test_with_a_lock_what_was_saved_in_memory_is_kept() -> None:
    lock = locked("lock")
    checkpoint = Checkpoint("dummy", lock)
    await checkpoint.save(NOW, 0)

    assert await checkpoint.acquire(NOW + timedelta(minutes=1))

    assert (checkpoint.time(), checkpoint.from_(), checkpoint.index()) == (NOW, NOW, 0)


async def test_a_lock_held_elsewhere_is_not_acquired() -> None:
    store = InMemoryStore()
    elsewhere = locked("locked", store)
    assert await elsewhere.acquire()

    assert not await Checkpoint("locked", locked("locked", store)).acquire(NOW)


async def test_saving_writes_the_time_the_index_and_the_start() -> None:
    cache = ArrayAdapter()
    checkpoint = Checkpoint("cache", NoLock(), cache)
    started = NOW - timedelta(hours=1)
    _ = await checkpoint.acquire(started)

    await checkpoint.save(NOW, 3)

    assert (checkpoint.time(), checkpoint.index(), checkpoint.from_()) == (NOW, 3, started)
    assert await stored(cache, "cache") == (NOW, 3, started)


async def test_a_full_cycle_with_a_cache() -> None:
    cache = ArrayAdapter()
    await put(cache, "cache", (NOW - timedelta(minutes=1), 3))
    checkpoint = Checkpoint("cache", NoLock(), cache)

    assert await checkpoint.acquire(NOW)
    assert (checkpoint.time(), checkpoint.index()) == (NOW - timedelta(minutes=1), 3)
    await checkpoint.save(NOW, 0)
    await checkpoint.release(NOW, None)

    assert await stored(cache, "cache") == (NOW, 0, NOW)


async def test_winning_the_lock_back_forgets_what_it_remembered() -> None:
    store = InMemoryStore()
    elsewhere = locked("locked", store)
    assert await elsewhere.acquire()
    lock = locked("locked", store)
    checkpoint = Checkpoint("locked", lock)
    await checkpoint.save(NOW - timedelta(minutes=2), 0)
    assert not await checkpoint.acquire(NOW - timedelta(minutes=1))
    await elsewhere.release()

    assert await checkpoint.acquire(NOW)

    assert (checkpoint.time(), checkpoint.index()) == (NOW, -1)
    assert await lock.is_acquired()


async def test_winning_the_lock_back_trusts_the_cache() -> None:
    store = InMemoryStore()
    elsewhere = locked("locked", store)
    assert await elsewhere.acquire()
    lock = locked("locked", store)
    cache = ArrayAdapter()
    checkpoint = Checkpoint("locked", lock, cache)
    saved = NOW - timedelta(minutes=2)
    await checkpoint.save(saved, 0)
    assert not await checkpoint.acquire(NOW - timedelta(minutes=1))
    other = Checkpoint("locked", lock, cache)
    await elsewhere.release()

    assert await other.acquire(NOW)

    assert (other.time(), other.index()) == (saved, 0)


async def test_a_state_that_cannot_be_saved_fails_loudly() -> None:
    cache = FlakyCache()
    cache.failure = "readonly"

    with pytest.raises(SchedulerRuntimeError, match='Failed to save the "cache" scheduler'):
        _ = await Checkpoint("cache", NoLock(), cache).acquire(NOW)


async def test_the_lock_is_kept_until_the_next_run() -> None:
    lock = locked("lock")
    checkpoint = Checkpoint("dummy", lock)
    _ = await checkpoint.acquire(NOW - timedelta(minutes=1))

    await checkpoint.release(NOW, NOW + timedelta(minutes=1))

    assert await lock.is_acquired()


async def test_the_lock_is_released_when_nothing_runs_again() -> None:
    lock = locked("lock")
    checkpoint = Checkpoint("dummy", lock)
    _ = await checkpoint.acquire(NOW - timedelta(minutes=1))

    await checkpoint.release(NOW, None)

    assert not await lock.is_acquired()


async def test_the_lock_is_refreshed_to_outlive_the_next_run() -> None:
    lock = RecordingLock(remaining=120.0)
    checkpoint = Checkpoint("dummy", lock)
    _ = await checkpoint.acquire(NOW - timedelta(seconds=10))

    await checkpoint.release(NOW, NOW + timedelta(seconds=60))

    assert (lock.refreshed, lock.released) == ([180.0], 0)


@pytest.mark.parametrize(
    ("remaining", "next_in"),
    [(-190.0, timedelta(seconds=60)), (0.0, timedelta(seconds=60)), (None, timedelta(1))],
)
async def test_a_lock_that_lapsed_or_never_expires_is_not_refreshed(
    remaining: float | None, next_in: timedelta
) -> None:
    lock = RecordingLock(remaining=remaining)
    checkpoint = Checkpoint("dummy", lock)
    _ = await checkpoint.acquire(NOW - timedelta(seconds=10))

    await checkpoint.release(NOW, NOW + next_in)

    assert (lock.refreshed, lock.released) == ([], 0)


async def test_a_lifetime_too_short_for_a_store_is_raised_to_the_least_one() -> None:
    lock = RecordingLock(remaining=0.4)
    checkpoint = Checkpoint("dummy", lock)
    _ = await checkpoint.acquire(NOW - timedelta(seconds=10))

    await checkpoint.release(NOW, NOW + timedelta(milliseconds=500))

    assert (lock.refreshed, lock.released) == ([1.0], 0)


async def test_the_saved_state_outlives_the_pool_s_default_lifetime() -> None:
    cache = ArrayAdapter(default_lifetime=1)
    checkpoint = Checkpoint("cache", NoLock(), cache)
    _ = await checkpoint.acquire(NOW)

    await checkpoint.save(NOW, 5)

    expiry = (await cache.get_item("cache")).metadata.get("expiry")
    assert expiry is not None
    assert expiry > time.time() + 365 * 86400


async def test_reading_before_acquiring_is_a_mistake() -> None:
    with pytest.raises(SchedulerRuntimeError, match="before it was acquired"):
        _ = Checkpoint("dummy").time()


async def test_closing_gives_the_lock_back_so_another_process_takes_over() -> None:
    store = InMemoryStore()
    lock = locked("locked", store)
    checkpoint = Checkpoint("locked", lock)
    _ = await checkpoint.acquire(NOW)
    await checkpoint.release(NOW, NOW + timedelta(minutes=1))

    await checkpoint.close()

    assert not await lock.is_acquired()
    assert await Checkpoint("locked", locked("locked", store)).acquire(NOW)


async def test_closing_leaves_a_lock_held_by_another_process_alone() -> None:
    store = InMemoryStore()
    elsewhere = locked("locked", store)
    assert await elsewhere.acquire()
    checkpoint = Checkpoint("locked", locked("locked", store))
    assert not await checkpoint.acquire(NOW)

    await checkpoint.close()

    assert await elsewhere.is_acquired()


async def test_closing_without_a_lock_does_nothing() -> None:
    await Checkpoint("dummy").close()
