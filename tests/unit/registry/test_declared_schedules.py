"""The declared schedules and task targets, for an application with no container."""

from __future__ import annotations

import pytest
from typing_extensions import override

from tests.support.messages import Plain
from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_periodic_task, as_schedule
from xtr_scheduler.registry import (
    ScheduleWithTasks,
    TaskDeclaration,
    declared_schedules,
    declared_task_targets,
    schedule_of,
    task_name,
)

pytestmark = pytest.mark.anyio


@as_schedule("tests-declared")
class DeclaredSchedule(ScheduleProviderInterface):
    """A provider built with no arguments."""

    def __init__(self) -> None:
        self._schedule: Schedule = Schedule(RecurringMessage.every(60, Plain()))

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule


@as_periodic_task(60, schedule="tests-declared")
class JoinsDeclared:
    """A task joining the declared provider's schedule."""

    def __call__(self) -> str:
        return "joined"


@as_periodic_task(60, schedule="tests-declared-bare")
def bare_task() -> str:
    return "bare"


def test_tasks_join_a_provider_s_schedule_or_get_one_of_their_own() -> None:
    provider = Schedule()
    tasks = [("app.A", TaskDeclaration(kind="every", frequency=60))]

    joined = schedule_of(provider, tasks)
    own = schedule_of(None, tasks)

    assert isinstance(joined, ScheduleWithTasks)
    assert joined.get_schedule() is provider
    assert isinstance(own, Schedule)
    assert len(own.recurring_messages) == 1
    assert schedule_of(provider, []) is provider


async def test_the_declared_schedules_are_built_with_their_tasks() -> None:
    schedules = declared_schedules()

    declared = (await schedules.get("tests-declared")).get_schedule()
    bare = (await schedules.get("tests-declared-bare")).get_schedule()

    assert len(declared.recurring_messages) == 2
    assert len(bare.recurring_messages) == 1


async def test_the_declared_targets_are_classes_built_and_functions_as_they_are() -> None:
    targets = declared_task_targets()

    assert isinstance(await targets.get(task_name(JoinsDeclared)), JoinsDeclared)
    assert await targets.get(task_name(bare_task)) is bare_task


async def test_only_the_schedule_asked_for_is_built() -> None:
    schedules = declared_schedules()

    assert schedules.has("tests-declared")
    assert not schedules.has("nope")
    assert await schedules.get("tests-declared") is await schedules.get("tests-declared")
