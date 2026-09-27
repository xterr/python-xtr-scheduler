"""A scheduled message was handled."""

from __future__ import annotations

from tests.support.contexts import a_context
from xtr_scheduler import Schedule
from xtr_scheduler.event import PostRunEvent


def test_it_carries_the_result() -> None:
    event = PostRunEvent(Schedule(), a_context(), "message", 42)

    assert (event.message, event.result) == ("message", 42)
    assert PostRunEvent(Schedule(), a_context(), "message").result is None
