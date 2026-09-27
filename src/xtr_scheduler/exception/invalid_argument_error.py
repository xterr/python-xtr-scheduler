"""A value handed to the scheduler cannot be used."""

from __future__ import annotations

from .scheduler_error import SchedulerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(SchedulerError, ValueError):
    """A value handed to the scheduler cannot be used: an interval, a date, a schedule name."""
