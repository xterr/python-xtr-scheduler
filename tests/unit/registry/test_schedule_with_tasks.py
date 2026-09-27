"""A schedule provider whose schedule also runs declared tasks."""

from __future__ import annotations

from tests.support.messages import Plain
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.registry import ScheduleWithTasks


def test_the_tasks_join_the_provider_s_schedule_once() -> None:
    own = RecurringMessage.every(60, Plain(1))
    task = RecurringMessage.every(60, Plain(2))
    schedule = Schedule(own)
    joined = ScheduleWithTasks(schedule, [task])

    assert joined.get_schedule() is schedule
    assert joined.get_schedule().recurring_messages == (own, task)
    assert joined.inner is schedule
