"""Spreads another trigger's runs by a random delay."""

from __future__ import annotations

import random
from datetime import timedelta

import pytest

from tests.support.dates import at
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger import CallbackTrigger, JitterTrigger, PeriodicalTrigger


def test_every_delay_is_within_the_bound_and_they_vary() -> None:
    time = at("2026-01-01T10:00:00+00:00")
    trigger = JitterTrigger(CallbackTrigger(lambda _run: time, "fixed"))

    runs = [trigger.get_next_run_date(time - timedelta(seconds=61)) for _ in range(100)]

    delays = {(run - time).total_seconds() for run in runs if run is not None}
    assert len(delays) > 1
    assert all(0 <= delay <= 60 for delay in delays)


def test_a_delayed_run_does_not_skip_the_next_one() -> None:
    start = at("2026-07-07T16:30:00+00:00")
    trigger = JitterTrigger(PeriodicalTrigger(10, start), 15)

    next_run = trigger.get_next_run_date(start + timedelta(seconds=12))

    assert next_run is not None
    assert start + timedelta(seconds=20) <= next_run <= start + timedelta(seconds=35)


def test_the_delay_comes_from_the_random_source_given() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    first = JitterTrigger(PeriodicalTrigger(60, start), random_source=random.Random(7))
    second = JitterTrigger(PeriodicalTrigger(60, start), random_source=random.Random(7))

    assert first.get_next_run_date(start) == second.get_next_run_date(start)


def test_runs_do_not_drift_by_the_delays() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    trigger = JitterTrigger(PeriodicalTrigger(60, start), 30)
    run = start
    for minute in range(1, 20):
        next_run = trigger.get_next_run_date(run)
        assert next_run is not None
        slot = start + timedelta(minutes=minute)
        assert slot <= next_run <= slot + timedelta(seconds=30)
        run = next_run


def test_a_stalled_inner_trigger_does_not_loop_forever() -> None:
    time = at("2026-01-01T10:00:00+00:00")
    trigger = JitterTrigger(CallbackTrigger(lambda _run: time, "stalled"), 5)

    next_run = trigger.get_next_run_date(time)

    assert next_run is not None
    assert time <= next_run <= time + timedelta(seconds=5)


def test_an_inner_trigger_that_ends_ends_the_jitter_too() -> None:
    trigger = JitterTrigger(CallbackTrigger(lambda _run: None, "never"))

    assert trigger.get_next_run_date(at("2026-01-01T10:00:00+00:00")) is None


def test_it_describes_itself_through_what_it_wraps() -> None:
    trigger = JitterTrigger(PeriodicalTrigger(20, "2026-01-01T00:00:00+00:00"), 15)

    assert str(trigger) == "every 20 seconds with 0-15 second jitter"


def test_a_bound_that_is_not_positive_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="max_seconds"):
        _ = JitterTrigger(PeriodicalTrigger(20), 0)
