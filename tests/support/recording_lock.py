"""A lock that is always free, reports a scripted lifetime, and records what it was asked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import override
from xtr_lock import LockInterface

if TYPE_CHECKING:
    from types import TracebackType


@final
class RecordingLock(LockInterface):
    """Acquires every time; :meth:`get_remaining_lifetime` answers ``remaining``."""

    def __init__(self, remaining: float | None) -> None:
        self.remaining = remaining
        self.refreshed: list[float | None] = []
        self.released = 0

    @override
    async def acquire(self, blocking: bool = False) -> bool:
        return True

    @override
    async def refresh(self, ttl: float | None = None) -> None:
        self.refreshed.append(ttl)

    @override
    async def is_acquired(self) -> bool:
        return True

    @override
    async def release(self) -> None:
        self.released += 1

    @override
    def is_expired(self) -> bool:
        return False

    @override
    def get_remaining_lifetime(self) -> float | None:
        return self.remaining

    @override
    async def __aenter__(self) -> Self:
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.release()
