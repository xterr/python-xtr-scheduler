"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["SchedulerError"]


class SchedulerError(Exception):
    """Something the scheduler could not do — catch this to catch them all."""
