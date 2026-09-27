"""Every error this package raises derives from one."""

from __future__ import annotations

from xtr_scheduler.exception import (
    InvalidArgumentError,
    SchedulerError,
    SchedulerLogicError,
    SchedulerRuntimeError,
)


def test_every_error_is_a_scheduler_error_and_a_standard_one_where_it_fits() -> None:
    assert issubclass(InvalidArgumentError, SchedulerError)
    assert issubclass(InvalidArgumentError, ValueError)
    assert issubclass(SchedulerLogicError, SchedulerError)
    assert issubclass(SchedulerRuntimeError, SchedulerError)
    assert issubclass(SchedulerRuntimeError, RuntimeError)
