"""Marks a message as produced by a schedule, and for which run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import final

from xtr_messenger import StampInterface, as_stamp

from xtr_scheduler.generator.message_context import MessageContext
from xtr_scheduler.trigger.serialized_trigger import SerializedTrigger

__all__ = ["ScheduledStamp"]


@as_stamp
@final
@dataclass(frozen=True, slots=True)
class ScheduledStamp(StampInterface):
    """The run a scheduled message belongs to.

    It travels with the message — through a redispatch to another transport,
    and across a broker — so the worker that handles it can say which
    schedule and which run it came from. The trigger travels as its
    description: triggers hold functions and parsed expressions that cannot
    cross a transport, and a listener needs only to know what it was.

    Attributes:
        name: The schedule's name.
        id: The recurring message's id within the schedule.
        trigger: How the trigger describes itself.
        triggered_at: When the run was due.
        next_trigger_at: When the recurring message runs next, if it does.
    """

    name: str
    id: str
    trigger: str
    triggered_at: datetime
    next_trigger_at: datetime | None = None

    @classmethod
    def from_context(cls, context: MessageContext) -> ScheduledStamp:
        """Record the run ``context`` describes."""
        return cls(
            context.name,
            context.id,
            str(context.trigger),
            context.triggered_at,
            context.next_trigger_at,
        )

    @property
    def message_context(self) -> MessageContext:
        """Return the run, its trigger standing in as a :class:`SerializedTrigger`."""
        return MessageContext(
            self.name,
            self.id,
            SerializedTrigger(self.trigger),
            self.triggered_at,
            self.next_trigger_at,
        )
