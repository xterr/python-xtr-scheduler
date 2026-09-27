"""A message generator whose schedule provider is looked up on first use."""

from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler.generator.message_generator import MessageGenerator
from xtr_scheduler.generator.message_generator_interface import MessageGeneratorInterface

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_clock import ClockInterface

    from xtr_scheduler.generator.message_context import MessageContext
    from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

__all__ = ["LocatedMessageGenerator"]


@final
class LocatedMessageGenerator(MessageGeneratorInterface):
    """Looks the schedule provider up the first time messages are asked for.

    A transport is built synchronously, while a container builds a provider
    asynchronously — and building a provider may be the first thing that
    touches the application's services. Deferring it to the first poll keeps
    building a transport free of both.
    """

    __slots__ = ("_clock", "_generator", "_name", "_providers")

    def __init__(
        self,
        providers: ScheduleProviderLocator,
        name: str,
        clock: ClockInterface | None = None,
    ) -> None:
        """Generate for the schedule ``providers`` has under ``name``."""
        self._providers = providers
        self._name = name
        self._clock = clock
        self._generator: MessageGenerator | None = None

    @override
    async def get_messages(self) -> AsyncGenerator[tuple[MessageContext, object]]:
        if self._generator is None:
            provider = await self._providers.get(self._name)
            self._generator = MessageGenerator(provider, self._name, self._clock)
        async with aclosing(self._generator.get_messages()) as messages:
            async for pair in messages:
                yield pair

    @override
    async def close(self) -> None:
        if self._generator is not None:
            await self._generator.close()
