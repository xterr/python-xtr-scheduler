"""Declare the provider of a schedule."""

from __future__ import annotations

import pytest
from typing_extensions import override

from xtr_scheduler import Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule
from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.registry import declared_schedules, schedules_declared_on

pytestmark = pytest.mark.anyio


@as_schedule("tests-as-schedule")
class ProvidedSchedule(ScheduleProviderInterface):
    """A provider declared at import."""

    @override
    def get_schedule(self) -> Schedule:
        return Schedule()


def test_the_class_is_recorded_on_itself_and_for_the_process() -> None:
    assert schedules_declared_on(ProvidedSchedule) == ("tests-as-schedule",)


def test_a_subclass_does_not_inherit_the_declaration() -> None:
    class Derived(ProvidedSchedule):
        pass

    assert schedules_declared_on(Derived) == ()


def test_declaring_the_same_class_again_is_harmless() -> None:
    assert as_schedule("tests-as-schedule")(ProvidedSchedule) is ProvidedSchedule


async def test_two_classes_for_one_schedule_are_refused_when_the_schedule_is_read() -> None:
    class Other(ScheduleProviderInterface):
        @override
        def get_schedule(self) -> Schedule:
            return Schedule()

    _ = as_schedule("tests-as-schedule-twice")(ProvidedSchedule)
    _ = as_schedule("tests-as-schedule-twice")(Other)

    with pytest.raises(SchedulerLogicError, match='"tests-as-schedule-twice" is provided by'):
        _ = await declared_schedules().get("tests-as-schedule-twice")
