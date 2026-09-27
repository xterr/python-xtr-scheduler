"""Which run of which recurring message a message belongs to."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import final

from xtr_scheduler.trigger.trigger_interface import TriggerInterface

__all__ = ["MessageContext"]


@final
@dataclass(frozen=True, slots=True)
class MessageContext:
    """Describes the run a message was produced for.

    Attributes:
        name: The schedule's name.
        id: The recurring message's id within the schedule.
        trigger: The trigger that fired.
        triggered_at: When the run was due — not when it happened, which is
            later after downtime.
        next_trigger_at: When the recurring message runs next, if it does.
    """

    name: str
    id: str
    trigger: TriggerInterface
    triggered_at: datetime
    next_trigger_at: datetime | None
