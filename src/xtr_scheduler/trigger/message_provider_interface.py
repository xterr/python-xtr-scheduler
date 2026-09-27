"""What a recurring message produces each time it runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_scheduler.generator.message_context import MessageContext

__all__ = ["MessageProviderInterface"]


@runtime_checkable
class MessageProviderInterface(Protocol):
    """Produces the messages of one run.

    Usually one fixed message; a provider may produce several, or decide per
    run — one message per active tenant, say.
    """

    @property
    def id(self) -> str:
        """Return what identifies this provider among a schedule's, stable across processes."""
        ...

    def get_messages(self, context: MessageContext, /) -> AsyncIterator[object]:
        """Yield the messages of the run ``context`` describes."""
        ...
