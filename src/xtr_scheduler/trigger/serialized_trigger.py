"""What a trigger is once it has crossed a transport: its description."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler.exception import SchedulerLogicError

from .trigger_interface import TriggerInterface

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["SerializedTrigger"]


@final
class SerializedTrigger(TriggerInterface):
    """A trigger's description, standing in for the trigger where it cannot travel.

    Triggers hold functions and parsed expressions that do not survive a
    transport. What travels is what a listener on the other side needs — the
    description — and this is what it reads back as.
    """

    __slots__ = ("_description",)

    def __init__(self, description: str) -> None:
        """Stand in for the trigger described as ``description``."""
        self._description = description

    @override
    def __str__(self) -> str:
        return self._description

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        """Refuse: a description cannot say when to run.

        Raises:
            SchedulerLogicError: Always.
        """
        raise SchedulerLogicError("Not possible to get next run date from a deserialized trigger.")
