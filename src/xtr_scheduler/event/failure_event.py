"""Dispatched when handling a scheduled message raised."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_scheduler.generator.message_context import MessageContext
    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

__all__ = ["FailureEvent"]


@final
class FailureEvent(Event):
    """Handling a scheduled message raised :attr:`error`.

    With the standalone :class:`~xtr_scheduler.scheduler.Scheduler`, a
    listener may ask for the error to be ignored instead of raised. Through a
    messenger worker the event only reports it: the worker has already dealt
    with the failure its own way.
    """

    def __init__(
        self,
        schedule: ScheduleProviderInterface,
        context: MessageContext,
        message: object,
        error: BaseException,
    ) -> None:
        """Describe ``message``, run for ``context`` of ``schedule``, whose handling raised."""
        self._schedule = schedule
        self._context = context
        self._message = message
        self._error = error
        self._should_ignore = False

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

    @property
    def error(self) -> BaseException:
        """Return what handling the message raised."""
        return self._error

    def should_ignore(self, value: bool | None = None) -> bool:
        """Return whether the error is ignored, first setting it when ``value`` is given."""
        if value is not None:
            self._should_ignore = value
        return self._should_ignore
