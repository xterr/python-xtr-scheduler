"""Declare a task run on a cron expression."""

from __future__ import annotations

from xtr_scheduler.decorator import as_cron_task
from xtr_scheduler.registry import TaskDeclaration, task_name, tasks_declared_on
from xtr_scheduler.registry.declarations import declared_tasks


@as_cron_task("0 3 * * *", timezone="Europe/Bucharest", schedule="tests-cron")
@as_cron_task("#daily", arguments=["eu"], jitter=30, transports="reports", env=["prod"])
class Reports:
    """A task class, declared twice."""

    def __call__(self, region: str = "all") -> str:
        return region


class Maintenance:
    """A class whose methods are tasks."""

    @as_cron_task("0 1 * * *")
    @as_cron_task("0 2 * * *")
    def purge(self) -> None: ...

    @as_cron_task("0 4 * * *")
    def vacuum(self) -> None: ...


@as_cron_task("*/5 * * * *")
async def ping() -> None: ...


def test_each_decoration_is_one_task_in_the_order_written() -> None:
    assert tasks_declared_on(Reports) == (
        TaskDeclaration(
            kind="cron",
            expression="#daily",
            jitter=30,
            arguments=("eu",),
            transports=("reports",),
            env=("prod",),
        ),
        TaskDeclaration(
            kind="cron", expression="0 3 * * *", timezone="Europe/Bucharest", schedule="tests-cron"
        ),
    )


def test_a_method_s_tasks_are_recorded_on_its_class_calling_that_method() -> None:
    declared = [(task.expression, task.method) for task in tasks_declared_on(Maintenance)]

    assert declared == [("0 2 * * *", "purge"), ("0 1 * * *", "purge"), ("0 4 * * *", "vacuum")]


def test_a_decorated_method_is_left_a_plain_method() -> None:
    assert callable(Maintenance.purge)
    assert Maintenance().purge() is None


def test_a_function_is_a_task_too() -> None:
    assert [task.expression for task in tasks_declared_on(ping)] == ["*/5 * * * *"]


def test_tasks_are_recorded_for_the_process_with_their_targets() -> None:
    targets = {task_name(target) for target, _declaration in declared_tasks()}

    assert {task_name(Reports), task_name(Maintenance), task_name(ping)} <= targets
    assert task_name(Reports) == f"{__name__}.Reports"
