"""What a task decorator declared."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, final

from xtr_messenger import RedispatchMessage

from xtr_scheduler.recurring_message import RecurringMessage

__all__ = ["TaskDeclaration"]


@final
@dataclass(frozen=True, slots=True)
class TaskDeclaration:
    """One ``@as_cron_task`` or ``@as_periodic_task``, as written.

    Attributes:
        kind: ``"cron"`` or ``"every"``.
        expression: The cron expression, for ``"cron"``.
        frequency: The interval, for ``"every"``.
        timezone: The zone a cron expression is read in.
        from_: When an interval starts counting.
        until: When an interval stops.
        jitter: The most a run is delayed at random, in seconds.
        arguments: What the target is called with.
        schedule: The schedule the task belongs to.
        method: The method called; ``None`` calls the target itself.
        transports: Where each run is sent instead of being handled where
            the schedule is consumed.
        env: The environments the task exists in; empty for all.
    """

    kind: Literal["cron", "every"]
    expression: str = ""
    frequency: int | float | str | timedelta = 0
    timezone: str | None = None
    from_: datetime | str | None = None
    until: datetime | str | None = None
    jitter: int | None = None
    arguments: tuple[object, ...] = ()
    schedule: str = "default"
    method: str | None = None
    transports: tuple[str, ...] = ()
    env: tuple[str, ...] = ()

    def on_method(self, method: str) -> TaskDeclaration:
        """Return this declaration calling ``method``."""
        return replace(self, method=method)

    def exists_in(self, environment: str) -> bool:
        """Tell whether the task exists in ``environment``."""
        return not self.env or environment in self.env

    def recurring_message(self, target: str) -> RecurringMessage:
        """Build the recurring message calling the task target named ``target``.

        Raises:
            InvalidArgumentError: If the interval, expression or a date
                cannot be used.
        """
        from xtr_scheduler.messenger.service_call_message import (  # noqa: PLC0415 — the messenger bridge imports this package
            ServiceCallMessage,
        )

        call = ServiceCallMessage(target, self.method or "__call__", self.arguments)
        message: object = RedispatchMessage(call, self.transports) if self.transports else call
        if self.kind == "cron":
            recurring = RecurringMessage.cron(self.expression, message, timezone=self.timezone)
        elif self.until is None:
            recurring = RecurringMessage.every(self.frequency, message, from_=self.from_)
        else:
            recurring = RecurringMessage.every(
                self.frequency, message, from_=self.from_, until=self.until
            )
        return recurring.with_jitter(self.jitter) if self.jitter else recurring
