"""The same messages on every run."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .message_provider_interface import MessageProviderInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from xtr_scheduler.generator.message_context import MessageContext

__all__ = ["StaticMessageProvider"]


@final
class StaticMessageProvider(MessageProviderInterface):
    """Produces the same messages on every run."""

    __slots__ = ("_description", "_id", "_messages")

    def __init__(self, messages: Iterable[object], id_: str = "", description: str = "") -> None:
        """Produce ``messages``, identified as ``id_`` and described as ``description``."""
        self._messages = tuple(messages)
        self._id = id_
        self._description = description

    @property
    @override
    def id(self) -> str:
        return self._id

    @override
    async def get_messages(self, context: MessageContext, /) -> AsyncIterator[object]:
        del context
        for message in self._messages:
            yield message

    @override
    def __str__(self) -> str:
        return self._description or self._id
