"""A set of recurring messages, and how they are run."""

from __future__ import annotations

import copy

import pytest
from xtr_cache.adapter import ArrayAdapter
from xtr_event_dispatcher import EventDispatcher
from xtr_lock import NoLock

from tests.support.messages import Plain
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.event import FailureEvent, PostRunEvent, PreRunEvent
from xtr_scheduler.exception import SchedulerLogicError


def every_minute(value: int = 0) -> RecurringMessage:
    return RecurringMessage.every(60, Plain(value), from_="2026-01-01T00:00:00+00:00")


def test_the_same_recurring_message_cannot_be_added_twice() -> None:
    schedule = Schedule(every_minute())

    with pytest.raises(SchedulerLogicError, match="Duplicated schedule message"):
        _ = schedule.add(every_minute())


def test_messages_keep_the_order_they_were_added_in() -> None:
    first, second = every_minute(1), every_minute(2)

    assert Schedule(first).add(second).recurring_messages == (first, second)


def test_changing_the_messages_asks_for_the_plan_to_be_rebuilt() -> None:
    first = every_minute(1)
    schedule = Schedule()
    assert not schedule.should_restart

    for change in (
        lambda: schedule.add(first),
        lambda: schedule.remove(first),
        lambda: schedule.remove_by_id("nope"),
        schedule.clear,
    ):
        schedule.set_restart(False)
        _ = change()
        assert schedule.should_restart


def test_removing_takes_the_message_out() -> None:
    first, second = every_minute(1), every_minute(2)
    schedule = Schedule(first, second)

    assert schedule.remove(first).recurring_messages == (second,)
    assert schedule.remove_by_id(second.id).recurring_messages == ()


def test_the_lock_the_state_and_catch_up_are_configured_fluently() -> None:
    lock, state = NoLock(), ArrayAdapter()

    schedule = Schedule().lock(lock).stateful(state).process_only_last_missed_run()

    assert schedule.get_lock() is lock
    assert schedule.get_state() is state
    assert schedule.should_process_only_last_missed_run()
    assert schedule.get_schedule() is schedule


def test_catching_up_on_the_latest_run_only_is_switched_on_by_default_and_off_by_asking() -> None:
    schedule = Schedule().process_only_last_missed_run()
    assert schedule.should_process_only_last_missed_run()

    assert not schedule.process_only_last_missed_run(False).should_process_only_last_missed_run()


def test_its_listeners_are_kept_on_the_schedule_itself() -> None:
    schedule = Schedule()
    assert schedule.event_dispatcher is None

    _ = schedule.before(lambda: None).after(lambda: None).on_failure(lambda: None)

    dispatcher = schedule.event_dispatcher
    assert isinstance(dispatcher, EventDispatcher)
    assert all(dispatcher.has_listeners(e) for e in (PreRunEvent, PostRunEvent, FailureEvent))


def test_a_copy_keeps_the_lock_and_state_and_has_its_own_messages_and_listeners() -> None:
    lock, state = NoLock(), ArrayAdapter()
    schedule = Schedule(every_minute(1)).lock(lock).stateful(state).before(lambda: None)

    copied = copy.copy(schedule)
    _ = copied.add(every_minute(2)).after(lambda: None)

    assert (copied.get_lock(), copied.get_state()) == (lock, state)
    assert len(schedule.recurring_messages) == 1
    assert len(copied.recurring_messages) == 2
    original, copied_dispatcher = schedule.event_dispatcher, copied.event_dispatcher
    assert isinstance(original, EventDispatcher)
    assert isinstance(copied_dispatcher, EventDispatcher)
    assert not original.has_listeners(PostRunEvent)
    assert copied_dispatcher.has_listeners(PreRunEvent)
