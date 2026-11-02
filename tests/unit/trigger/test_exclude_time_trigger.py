"""Skips another trigger's runs that fall in a window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.support.dates import at
from xtr_scheduler.trigger import CallbackTrigger, ExcludeTimeTrigger


def _one_second_later(run: datetime) -> datetime:
    return run + timedelta(seconds=1)


def test_runs_in_the_window_are_replaced_by_the_first_after_it() -> None:
    trigger = ExcludeTimeTrigger(
        CallbackTrigger(_one_second_later, "every second"),
        at("2020-02-20T02:02:02Z"),
        at("2020-02-20T20:20:20Z"),
    )

    assert trigger.get_next_run_date(at("2020-02-20T02:02:00Z")) == at("2020-02-20T02:02:01Z")
    assert trigger.get_next_run_date(at("2020-02-20T02:02:02Z")) == at("2020-02-20T20:20:21Z")
    assert trigger.get_next_run_date(at("2020-02-20T20:20:20Z")) == at("2020-02-20T20:20:21Z")
    assert trigger.get_next_run_date(at("2020-02-20T22:22:22Z")) == at("2020-02-20T22:22:23Z")


def test_a_run_before_the_window_is_kept_when_both_read_the_same_hour_a_clock_repeats() -> None:
    # Bucharest lives through 03:00-04:00 twice on 2026-10-25. The window is in the
    # second pass; 03:40 of the first pass is an hour before it, not inside it.
    bucharest = ZoneInfo("Europe/Bucharest")
    trigger = ExcludeTimeTrigger(
        CallbackTrigger(_one_second_later, "every second"),
        datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=bucharest),
        datetime(2026, 10, 25, 3, 50, fold=1, tzinfo=bucharest),
    )

    next_run = trigger.get_next_run_date(datetime(2026, 10, 25, 3, 39, 59, tzinfo=bucharest))

    # Through UTC: a date in a repeated hour never equals one on another zone.
    assert next_run is not None
    assert next_run.astimezone(UTC) == at("2026-10-25T00:40:00Z")


def test_an_inner_trigger_that_ends_is_passed_through() -> None:
    trigger = ExcludeTimeTrigger(
        CallbackTrigger(lambda _run: None, "never"),
        "2020-02-20T00:00:00Z",
        "2020-02-21T00:00:00Z",
    )

    assert trigger.get_next_run_date(at("2020-02-20T12:00:00Z")) is None


def test_it_describes_the_window() -> None:
    trigger = ExcludeTimeTrigger(
        CallbackTrigger(_one_second_later, "every second"),
        "2020-02-20T02:02:02+00:00",
        "2020-02-20T20:20:20+02:00",
    )

    assert str(trigger) == (
        "every second, excluding from 2020-02-20T02:02:02+00:00 until 2020-02-20T20:20:20+02:00"
    )
