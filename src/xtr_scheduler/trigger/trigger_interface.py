"""When a recurring message runs next."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["TriggerInterface"]


@runtime_checkable
class TriggerInterface(Protocol):
    """Says when a recurring message runs next.

    Its string form describes it — what ``debug:scheduler`` shows — and is
    part of the recurring message's identity, so two triggers that describe
    themselves alike are the same trigger.
    """

    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        """Return the next run strictly after ``run``, or ``None`` when there is none.

        Strictly after is what the scheduler relies on to move forward: a
        trigger returning ``run`` itself, or an earlier date, is refused.
        """
        ...

    @override
    def __str__(self) -> str:
        """Describe the trigger."""
        ...
