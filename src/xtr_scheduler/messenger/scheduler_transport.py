"""A transport that receives a schedule's messages as they fall due."""

from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import Clock
from xtr_messenger import Envelope, ReceivedStamp, RedispatchMessage, TransportInterface

from xtr_scheduler.exception import SchedulerLogicError

from .scheduled_stamp import ScheduledStamp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_clock import ClockInterface

    from xtr_scheduler.generator.message_generator_interface import MessageGeneratorInterface

__all__ = ["SchedulerTransport"]

#: How often a schedule with nothing due is asked again, in seconds — also
#: how soon a message added to a running schedule is noticed.
DEFAULT_POLL_INTERVAL: Final = 1.0


@final
class SchedulerTransport(TransportInterface):
    """Receives a schedule's messages as they fall due; sends nothing.

    Each message arrives stamped with the run it belongs to
    (:class:`ScheduledStamp`). A message the schedule wraps in a
    :class:`~xtr_messenger.RedispatchMessage` — and every message, with
    ``use_messenger_routing`` — is handed to the worker to dispatch again, so
    routing sends it on to where it is handled; otherwise the worker consuming
    this transport handles it.

    Settling is a no-op: the schedule records each message as sent the moment
    the worker asks for the next one, whatever becomes of it.
    """

    __slots__ = ("_clock", "_generator", "_name", "_poll_interval", "_use_messenger_routing")

    def __init__(
        self,
        generator: MessageGeneratorInterface,
        *,
        name: str = "scheduler",
        use_messenger_routing: bool = False,
        clock: ClockInterface | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Receive what ``generator`` produces, as the transport ``name``.

        ``poll_interval`` is how long to wait before asking again when
        nothing was due, on ``clock``.
        """
        self._generator = generator
        self._name = name
        self._use_messenger_routing = use_messenger_routing
        self._clock: ClockInterface = clock if clock is not None else Clock()
        self._poll_interval = poll_interval

    @property
    def generator(self) -> MessageGeneratorInterface:
        """Return what produces the messages."""
        return self._generator

    @override
    async def get(self) -> AsyncGenerator[Envelope]:
        """Yield messages as they fall due, never stopping on its own.

        Stops only when the worker stops asking — which a worker's ``stop()``
        does while this waits — and then hands the schedule back, its lock
        released, so another process can take over at once.
        """
        try:
            while True:
                received = False
                async with aclosing(self._generator.get_messages()) as due:
                    async for context, message in due:
                        received = True
                        yield self._envelope(ScheduledStamp.from_context(context), message)
                if not received:
                    await self._clock.sleep_async(self._wait())
        finally:
            await self._generator.close()

    def _wait(self) -> float:
        """Return the wait before the next poll: the interval, or less if a run is due sooner.

        A next run already behind means nothing was read from the schedule —
        another process holds its lock, or the schedule was just reloaded — so
        this waits the whole interval rather than asking again at once, which
        would spin on the lock store.
        """
        until = self._generator.wait_until
        if until is None:
            return self._poll_interval
        remaining = (until - self._clock.now()).total_seconds()
        if remaining <= 0:
            return self._poll_interval
        return min(self._poll_interval, remaining)

    @override
    async def ack(self, envelope: Envelope) -> None:
        """Nothing to do: the schedule already recorded the message as sent."""
        del envelope

    @override
    async def reject(self, envelope: Envelope) -> None:
        """Nothing to do: a scheduled message is not delivered again."""
        del envelope

    @override
    async def send(self, envelope: Envelope) -> Envelope:
        """Refuse: messages come from the schedule, never from a sender.

        Raises:
            SchedulerLogicError: Always.
        """
        del envelope
        raise SchedulerLogicError(f'"{type(self).__name__}" cannot send messages.')

    def _envelope(self, stamp: ScheduledStamp, message: object) -> Envelope:
        if isinstance(message, RedispatchMessage):
            message = RedispatchMessage(
                Envelope.wrap(message.envelope, [stamp]), message.transport_names
            )
        elif self._use_messenger_routing:
            message = RedispatchMessage(Envelope.wrap(message, [stamp]))
        return Envelope(message, (stamp, ReceivedStamp(self._name)))
