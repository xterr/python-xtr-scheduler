"""Asks for a method of a scheduled task to be called."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override
from xtr_messenger import as_message

__all__ = ["ServiceCallMessage"]


@as_message(name="xtr_scheduler.service_call.v1")
@final
@dataclass(frozen=True, slots=True)
class ServiceCallMessage:
    """Call ``method`` of the task target named ``service``, with ``arguments``.

    What a task declared with
    :func:`~xtr_scheduler.decorator.as_cron_task` or
    :func:`~xtr_scheduler.decorator.as_periodic_task` sends each time it
    runs. It crosses transports like any declared message, so the arguments
    must be JSON values — a task sent to another worker is called there.

    Attributes:
        service: The name the target is known under.
        method: The method to call; ``__call__`` calls the target itself.
        arguments: Positional arguments for the call — JSON values.
    """

    service: str
    method: str = "__call__"
    arguments: tuple[object, ...] = ()

    @override
    def __str__(self) -> str:
        """Describe the call as ``@service`` or ``@service::method``."""
        return f"@{self.service}" + ("" if self.method == "__call__" else f"::{self.method}")
