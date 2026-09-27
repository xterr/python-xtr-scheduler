"""Something the scheduler depends on failed while it ran."""

from __future__ import annotations

from .scheduler_error import SchedulerError

__all__ = ["SchedulerRuntimeError"]


class SchedulerRuntimeError(SchedulerError, RuntimeError):
    """Something the scheduler depends on failed while it ran — a cache that cannot save."""
