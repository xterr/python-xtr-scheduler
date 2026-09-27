"""What a trigger is once it has crossed a transport."""

from __future__ import annotations

import pytest

from tests.support.dates import at
from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.trigger import SerializedTrigger


def test_it_is_its_description() -> None:
    assert str(SerializedTrigger("every 10 seconds")) == "every 10 seconds"


def test_it_cannot_say_when_to_run() -> None:
    with pytest.raises(SchedulerLogicError, match="deserialized trigger"):
        _ = SerializedTrigger("x").get_next_run_date(at("2026-01-01T00:00:00+00:00"))
