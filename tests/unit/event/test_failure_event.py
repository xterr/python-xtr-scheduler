"""Handling a scheduled message raised."""

from __future__ import annotations

from tests.support.contexts import a_context
from xtr_scheduler import Schedule
from xtr_scheduler.event import FailureEvent


def test_the_error_is_raised_unless_a_listener_ignores_it() -> None:
    error = ValueError("boom")
    event = FailureEvent(Schedule(), a_context(), "message", error)

    assert event.error is error
    assert event.should_ignore() is False
    assert event.should_ignore(value=True) is True
