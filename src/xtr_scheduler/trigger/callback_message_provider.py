"""Messages a function decides on at each run."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Awaitable, Iterable
from typing import TYPE_CHECKING, TypeAlias, final

from typing_extensions import override

from .message_provider_interface import MessageProviderInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from xtr_scheduler.generator.message_context import MessageContext

__all__ = ["CallbackMessageProvider", "Produced"]

Produced: TypeAlias = "Iterable[object] | AsyncIterable[object] | Awaitable[Iterable[object]]"
"""What the callback may return: messages, an async generator of them, or a coroutine of them."""


@final
class CallbackMessageProvider(MessageProviderInterface):
    """Asks ``callback`` for the messages of each run.

    For runs whose messages depend on the moment — one message per active
    tenant, say. The callback is a plain function, a coroutine function, or
    an async generator function.
    """

    __slots__ = ("_callback", "_description", "_id")

    def __init__(
        self,
        callback: Callable[[MessageContext], Produced],
        id_: str = "",
        description: str = "",
    ) -> None:
        """Ask ``callback`` for each run's messages; identify and describe the provider."""
        self._callback = callback
        self._id = id_
        self._description = description

    @property
    @override
    def id(self) -> str:
        return self._id

    @override
    async def get_messages(self, context: MessageContext, /) -> AsyncIterator[object]:
        produced = self._callback(context)
        if inspect.isawaitable(produced):
            produced = await produced
        if isinstance(produced, AsyncIterable):
            async for message in produced:
                yield message
            return
        for message in produced:
            yield message

    @override
    def __str__(self) -> str:
        return self._description or self._id
