"""What produces a schedule's messages as they fall due."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .message_context import MessageContext

__all__ = ["MessageGeneratorInterface"]


@runtime_checkable
class MessageGeneratorInterface(Protocol):
    """Produces the messages that are due, each with the run it belongs to."""

    def get_messages(self) -> AsyncGenerator[tuple[MessageContext, object]]:
        """Yield every message due by now, then stop.

        A generator, so a caller that stops early closes it (``aclose``) and
        what was sent so far is recorded.
        """
        ...

    async def close(self) -> None:
        """Stop generating for good: hand back what the schedule holds, such as its lock."""
        ...
