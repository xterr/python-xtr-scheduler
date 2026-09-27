"""Dispatched before a scheduled message is handled."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_scheduler.generator.message_context import MessageContext
    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

__all__ = ["PreRunEvent"]


@final
class PreRunEvent(Event):
    """A scheduled message is about to be handled; a listener may cancel the run."""

    def __init__(
        self,
        schedule: ScheduleProviderInterface,
        context: MessageContext,
        message: object,
    ) -> None:
        """Describe ``message``, produced for the run ``context`` of ``schedule``."""
        self._schedule = schedule
        self._context = context
        self._message = message
        self._should_cancel = False

    @property
    def schedule(self) -> ScheduleProviderInterface:
        """Return the schedule the message belongs to."""
        return self._schedule

    @property
    def context(self) -> MessageContext:
        """Return the run the message was produced for."""
        return self._context

    @property
    def message(self) -> object:
        """Return the message."""
        return self._message

    def should_cancel(self, value: bool | None = None) -> bool:
        """Return whether the run is cancelled, first setting it when ``value`` is given."""
        if value is not None:
            self._should_cancel = value
        return self._should_cancel
