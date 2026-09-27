"""Every error this package raises, each deriving from :class:`SchedulerError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .scheduler_error import SchedulerError
from .scheduler_logic_error import SchedulerLogicError
from .scheduler_runtime_error import SchedulerRuntimeError

__all__ = [
    "InvalidArgumentError",
    "SchedulerError",
    "SchedulerLogicError",
    "SchedulerRuntimeError",
]
