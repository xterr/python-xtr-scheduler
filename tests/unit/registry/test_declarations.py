"""What the scheduler's decorators recorded."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_scheduler.registry import declarations, schedules_declared_on, task_name, tasks_declared_on

if TYPE_CHECKING:
    import pytest


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


def test_reset_forgets_what_was_declared_and_keeps_the_marks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(declarations, "_SCHEDULES", {})
    monkeypatch.setattr(declarations, "_TASKS", [])

    class Provider:
        pass

    declarations.declare_schedule(Provider, "reports")

    declarations.reset_declarations()

    assert declarations.declared_schedule_names() == ()
    assert schedules_declared_on(Provider) == ("reports",)
