"""What the scheduler's decorators recorded."""

from __future__ import annotations

from xtr_scheduler.registry import schedules_declared_on, task_name, tasks_declared_on


def helper() -> None: ...


class Undecorated:
    """Nothing declared on it."""


def test_nothing_declared_reads_as_nothing() -> None:
    assert schedules_declared_on(Undecorated) == ()
    assert tasks_declared_on(Undecorated) == ()
    assert tasks_declared_on(42) == ()


def test_a_task_is_named_by_its_module_and_qualified_name() -> None:
    assert task_name(Undecorated) == f"{__name__}.Undecorated"
    assert task_name(helper) == f"{__name__}.helper"
    assert task_name(Undecorated()) == f"{__name__}.Undecorated"
