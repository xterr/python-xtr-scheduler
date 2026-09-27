"""How far a schedule got, kept in memory and optionally in a cache, under an optional lock."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_scheduler._time import microseconds
from xtr_scheduler.exception import SchedulerRuntimeError

from .checkpoint_interface import CheckpointInterface

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_cache_contracts import CacheInterface, ItemInterface, Metadata
    from xtr_lock import LockInterface

__all__ = ["Checkpoint"]

#: How long a saved checkpoint lives: long enough that it never lapses while
#: the schedule runs, short enough that an abandoned one is cleaned up.
CACHE_EXPIRY: Final = 5 * 365 * 86400

#: The shortest lifetime a lock is refreshed to; some stores refuse less.
_MINIMUM_TTL: Final = 1.0


@final
class Checkpoint(CheckpointInterface):
    """Records how far a schedule got.

    With no cache the record lives in this object, so a restarted process
    starts from the moment it started. With a cache it is saved there after
    every message, and a restarted process — or another one taking over —
    resumes from it.

    With a lock only the process holding it runs the schedule. A process that
    loses the lock and later wins it back trusts nothing it remembers, unless
    the cache says otherwise: another process ran the schedule meanwhile.
    """

    __slots__ = ("_cache", "_from", "_index", "_lock", "_name", "_reset", "_time")

    def __init__(
        self,
        name: str,
        lock: LockInterface | None = None,
        cache: CacheInterface | None = None,
    ) -> None:
        """Record under ``name``, coordinating through ``lock`` and saving to ``cache``."""
        self._name = name
        self._lock = lock
        self._cache = cache
        self._from: datetime | None = None
        self._time: datetime | None = None
        self._index = -1
        self._reset = False

    @override
    async def acquire(self, now: datetime, /) -> bool:
        if self._lock is not None and not await self._lock.acquire():
            # Another process has it, and what this one remembers will be stale
            # by the time it gets it back — unless a cache says where it got to.
            self._reset = True
            return False
        if self._cache is not None:

            async def fresh(item: ItemInterface) -> tuple[datetime, int, datetime]:
                _ = item.expires_after(CACHE_EXPIRY)
                return (now, -1, now)

            saved = await self._cache.get(self._name, fresh)
            self._time, self._index = saved[0], saved[1]
            self._from = saved[2] if len(saved) > 2 else now  # noqa: PLR2004 — (time, index[, from])
            await self.save(self._time, self._index)
        elif self._reset:
            self._reset = False
            await self.save(now, -1)
        if self._time is None:
            self._time = now
        if self._from is None:
            self._from = now
        return True

    @override
    def from_(self) -> datetime:
        return self._acquired(self._from)

    @override
    def time(self) -> datetime:
        return self._acquired(self._time)

    @override
    def index(self) -> int:
        return self._index

    @override
    async def save(self, time: datetime, index: int, /) -> None:
        """Record the message at ``index``, due at ``time``, as sent.

        Raises:
            SchedulerRuntimeError: If the cache could not save it. Carrying on
                would reload the old record on every tick and send nothing,
                or send again what was sent after a restart.
        """
        self._time = time
        self._index = index
        if self._from is None:
            self._from = time
        if self._cache is None:
            return
        state = (time, index, self._from)

        async def record(item: ItemInterface) -> tuple[datetime, int, datetime]:
            _ = item.expires_after(CACHE_EXPIRY)
            return state

        metadata: Metadata = {}
        _ = await self._cache.get(self._name, record, beta=float("inf"), metadata=metadata)
        if metadata.get("save_failed"):
            raise SchedulerRuntimeError(
                f'Failed to save the "{self._name}" scheduler checkpoint, '
                "the cache backend may be unavailable."
            )

    @override
    async def release(self, now: datetime, next_time: datetime | None, /) -> None:
        if self._lock is None:
            return
        if next_time is None:
            await self._lock.release()
            return
        remaining = self._lock.get_remaining_lifetime()
        # A lock that never expires needs no refresh; one that already lapsed
        # may be another process's by now, and is not fought over.
        if remaining is None or remaining <= 0:
            return
        # Keep the lock until the next run. The lock may have run out during a
        # long run, and stores refuse a lifetime that is negative or too short:
        # a lifetime too short is raised to the least one, never skipped.
        ttl = (microseconds(next_time) - microseconds(now)) / 1_000_000 + remaining
        await self._lock.refresh(max(ttl, _MINIMUM_TTL))

    @override
    async def close(self) -> None:
        """Release the lock, if this process holds it, so another can take over at once.

        Between runs the lock is kept until the next one is due; a process
        that stops for good gives it back rather than have the next process
        wait for it to run out.
        """
        if self._lock is not None and await self._lock.is_acquired():
            await self._lock.release()

    @staticmethod
    def _acquired(value: datetime | None) -> datetime:
        if value is None:
            raise SchedulerRuntimeError("The checkpoint was read before it was acquired.")
        return value
