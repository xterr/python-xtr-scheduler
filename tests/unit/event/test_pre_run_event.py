"""A scheduled message is about to be handled."""

from __future__ import annotations

from tests.support.contexts import a_context
from xtr_scheduler import Schedule
from xtr_scheduler.event import PreRunEvent


def test_a_run_goes_ahead_unless_a_listener_cancels_it() -> None:
    schedule, context = Schedule(), a_context()
    event = PreRunEvent(schedule, context, "message")

    assert (event.schedule, event.context, event.message) == (schedule, context, "message")
    assert event.should_cancel() is False
    assert event.should_cancel(value=True) is True
    assert event.should_cancel() is True
