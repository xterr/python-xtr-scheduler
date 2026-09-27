"""Turns a worker's events about a scheduled message into scheduler events."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_messenger import Envelope, HandledStamp, RedispatchMessage
from xtr_messenger.event import (
    WorkerMessageFailedEvent,
    WorkerMessageHandledEvent,
    WorkerMessageReceivedEvent,
)

from xtr_scheduler.event import FailureEvent, PostRunEvent, PreRunEvent
from xtr_scheduler.messenger.scheduled_stamp import ScheduledStamp
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_event_dispatcher_contracts import Event

    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

__all__ = ["DispatchSchedulerEventListener"]


@final
class DispatchSchedulerEventListener(EventSubscriberInterface):
    """Announces each scheduled run: before it, after it, and when it fails.

    Listens to the worker events of whichever worker handles the message —
    the one consuming the scheduler transport, or one the message was
    redispatched to, since the :class:`ScheduledStamp` travels with it. Each
    event goes to the application's dispatcher first, then to the listeners
    of the schedule itself (:meth:`Schedule.before
    <xtr_scheduler.schedule.Schedule.before>` and the like).

    A listener cancelling a run makes the worker skip the message; the
    listeners see the message the schedule produced, never the redispatch
    wrapped around it.
    """

    _EVENTS: ClassVar[Mapping[str | type, SubscribedEvents]] = {
        WorkerMessageReceivedEvent: "on_message_received",
        WorkerMessageHandledEvent: "on_message_handled",
        WorkerMessageFailedEvent: "on_message_failed",
    }

    __slots__ = ("_dispatcher", "_providers")

    def __init__(
        self,
        providers: ScheduleProviderLocator,
        event_dispatcher: EventDispatcherInterface,
    ) -> None:
        """Announce runs of the schedules in ``providers`` through ``event_dispatcher``."""
        self._providers = providers
        self._dispatcher = event_dispatcher

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return cls._EVENTS

    async def on_message_received(self, event: WorkerMessageReceivedEvent) -> None:
        """Announce the run; skip the message when a listener cancels it."""
        found = await self._scheduled(event.envelope)
        if found is None:
            return
        provider, stamp = found
        pre_run = PreRunEvent(provider, stamp.message_context, _message_of(event.envelope))
        await self._dispatch(provider, pre_run)
        if pre_run.should_cancel():
            _ = event.should_handle(value=False)

    async def on_message_handled(self, event: WorkerMessageHandledEvent) -> None:
        """Announce the run as done, with what handling it returned."""
        found = await self._scheduled(event.envelope)
        if found is None:
            return
        provider, stamp = found
        handled = event.envelope.last(HandledStamp)
        post_run = PostRunEvent(
            provider,
            stamp.message_context,
            _message_of(event.envelope),
            handled.result if handled is not None else None,
        )
        await self._dispatch(provider, post_run)

    async def on_message_failed(self, event: WorkerMessageFailedEvent) -> None:
        """Announce the run as failed; the worker deals with the failure itself."""
        found = await self._scheduled(event.envelope)
        if found is None:
            return
        provider, stamp = found
        failure = FailureEvent(
            provider, stamp.message_context, _message_of(event.envelope), event.error
        )
        await self._dispatch(provider, failure)

    async def _scheduled(
        self, envelope: Envelope
    ) -> tuple[ScheduleProviderInterface, ScheduledStamp] | None:
        """Return the provider and stamp of a message from a schedule known here."""
        stamp = envelope.last(ScheduledStamp)
        if stamp is None or not self._providers.has(stamp.name):
            return None
        return await self._providers.get(stamp.name), stamp

    async def _dispatch(self, provider: ScheduleProviderInterface, event: Event) -> None:
        _ = await self._dispatcher.dispatch(event)
        own = provider.get_schedule().event_dispatcher
        if own is not None:
            _ = await own.dispatch(event)


def _message_of(envelope: Envelope) -> object:
    """Return the message a schedule produced, unwrapped from a redispatch."""
    message = envelope.message
    if not isinstance(message, RedispatchMessage):
        return message
    return message.message
