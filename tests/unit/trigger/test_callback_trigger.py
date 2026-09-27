"""Runs whenever a function says."""

from __future__ import annotations

from datetime import datetime, timedelta

from tests.support.dates import at
from xtr_scheduler.trigger import CallbackTrigger


def _hour_later(run: datetime) -> datetime:
    return run + timedelta(hours=1)


def test_it_asks_the_callback() -> None:
    trigger = CallbackTrigger(_hour_later, "hourly")

    assert trigger.get_next_run_date(at("2026-01-01T00:00:00+00:00")) == at(
        "2026-01-01T01:00:00+00:00"
    )
    assert str(trigger) == "hourly"


def test_without_a_description_it_names_the_callback_by_identity() -> None:
    assert str(CallbackTrigger(_hour_later)) == str(id(_hour_later))
