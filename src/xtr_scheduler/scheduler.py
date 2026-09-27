"""Runs schedules in-process, without a message bus."""

from __future__ import annotations

import asyncio
import inspect
from contextlib import aclosing
from typing import TYPE_CHECKING, final

from xtr_clock import Clock

from .event import FailureEvent, PostRunEvent, PreRunEvent
from .generator.message_generator import MessageGenerator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from .generator.message_context import MessageContext
    from .schedule import Schedule

__all__ = ["Scheduler"]


@final
class Scheduler:
    """Runs schedules in this process, calling a handler per message type.

    For a process with no message bus: each message is handed straight to
    the handler registered for its exact type. With an event dispatcher,
    every run is announced — a :class:`PreRunEvent` listener may cancel it,
    and a :class:`FailureEvent` listener may ask for an error to be ignored
    rather than raised.

    Each schedule runs under its own generator, so its lock, state and
    catch-up settings apply as they would on a transport.
    """

    __slots__ = ("_clock", "_dispatcher", "_generators", "_handlers", "_index", "_stopped")

    def __init__(
        self,
        handlers: Mapping[type, Callable[[object], object]],
        schedules: Iterable[Schedule] = (),
        clock: ClockInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Run ``schedules``, handing each message to ``handlers[type(message)]``.

        A handler may be a coroutine function.
        """
        self._handlers = dict(handlers)
        self._clock: ClockInterface = clock if clock is not None else Clock()
        self._dispatcher = event_dispatcher
        self._generators: list[MessageGenerator] = []
        self._index = 0
        self._stopped = False
        for schedule in schedules:
            self.add_schedule(schedule)

    def add_schedule(self, schedule: Schedule) -> None:
        """Run ``schedule`` too, named ``schedule_<n>`` in the order added."""
        self.add_message_generator(
            MessageGenerator(schedule, f"schedule_{self._index}", self._clock)
        )
        self._index += 1

    def add_message_generator(self, generator: MessageGenerator) -> None:
        """Run what ``generator`` produces too."""
        self._generators.append(generator)

    async def run(self, sleep: float = 1.0) -> None:
        """Hand every due message to its handler until :meth:`stop` is called.

        When nothing ran, waits out the rest of ``sleep`` seconds before
        looking again; when something did, looks again at once, so a backlog
        after downtime is worked through without pauses.

        Raises:
            KeyError: If no handler is registered for a message's type.
            Exception: Whatever a handler raised, unless a failure listener
                ignored it.
        """
        self._stopped = False
        while not self._stopped:
            started = self._clock.now()
            ran = False
            for generator in self._generators:
                async with aclosing(generator.get_messages()) as due:
                    async for context, message in due:
                        ran = await self._run(generator, context, message) or ran
            if not ran:
                elapsed = (self._clock.now() - started).total_seconds()
                await self._clock.sleep_async(sleep - elapsed)
            else:
                await asyncio.sleep(0)

    def stop(self) -> None:
        """Stop :meth:`run` once the messages in hand are handled."""
        self._stopped = True

    async def _run(
        self, generator: MessageGenerator, context: MessageContext, message: object
    ) -> bool:
        """Handle ``message``; return whether its handler ran to completion."""
        handler = self._handlers[type(message)]
        if self._dispatcher is None:
            _ = await _called(handler, message)
            return True
        schedule = generator.schedule
        pre_run = await self._dispatcher.dispatch(PreRunEvent(schedule, context, message))
        if pre_run.should_cancel():
            return False
        try:
            result = await _called(handler, message)
        except Exception as error:
            failure = await self._dispatcher.dispatch(
                FailureEvent(schedule, context, message, error)
            )
            if not failure.should_ignore():
                raise
            return False
        _ = await self._dispatcher.dispatch(PostRunEvent(schedule, context, message, result))
        return True


async def _called(handler: Callable[[object], object], message: object) -> object:
    result = handler(message)
    return await result if inspect.isawaitable(result) else result
