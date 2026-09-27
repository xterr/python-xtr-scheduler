"""The scheduler was used in a way that cannot work."""

from __future__ import annotations

from .scheduler_error import SchedulerError

__all__ = ["SchedulerLogicError"]


class SchedulerLogicError(SchedulerError):
    """The scheduler was used in a way that cannot work, whatever the input.

    A trigger that does not move forward, a message added twice, a transport
    asked to send: each is a mistake in the code, not in the data.
    """
