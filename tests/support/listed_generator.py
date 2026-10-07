"""A message generator yielding prepared batches, one per call."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler.generator import MessageContext, MessageGeneratorInterface

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime


@final
class ListedGenerator(MessageGeneratorInterface):
    """Yields ``batches[0]`` on the first call, ``batches[1]`` on the next, then nothing."""

    def __init__(self, *batches: list[tuple[MessageContext, object]]) -> None:
        self._batches = list(batches)
        self.calls = 0
        self.closed = False
        self.next_due: datetime | None = None

    @property
    @override
    def wait_until(self) -> datetime | None:
        return self.next_due

    @override
    async def get_messages(self) -> AsyncGenerator[tuple[MessageContext, object]]:
        self.calls += 1
        batch = self._batches.pop(0) if self._batches else []
        for pair in batch:
            yield pair

    @override
    async def close(self) -> None:
        self.closed = True
