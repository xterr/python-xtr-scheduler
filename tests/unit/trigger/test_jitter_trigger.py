"""Spreads another trigger's runs by a random delay."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from tests.support.dates import at
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger import (
    CallbackTrigger,
    CronExpressionTrigger,
    JitterTrigger,
    PeriodicalTrigger,
)

_BUCHAREST = ZoneInfo("Europe/Bucharest")

_CLOCK_CHANGES = {
    # 03:00 does not happen on 2026-03-29: the clocks go from 03:00 to 04:00.
    "spring-forward": datetime(2026, 3, 27, 12, tzinfo=_BUCHAREST),
    # 03:00 happens twice on 2026-10-25: the clocks go from 04:00 back to 03:00.
    "fall-back": datetime(2026, 10, 23, 12, tzinfo=_BUCHAREST),
}
"""Noon a couple of days before each 2026 clock change in Bucharest."""

_NIGHTS = 6
"""Enough nights from each start to run through its clock change and out the other side."""


def test_every_delay_is_within_the_bound_and_they_vary() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    trigger = JitterTrigger(PeriodicalTrigger(3600, start))

    delays: set[float] = set()
    for hour in range(100):
        slot = start + timedelta(hours=hour)
        # Asked from past where the slot's own run can land, as a scheduler that sent it would.
        run = trigger.get_next_run_date(slot + timedelta(seconds=60))
        assert run is not None
        delays.add((run - (slot + timedelta(hours=1))).total_seconds())

    assert len(delays) > 1
    assert all(0 <= delay <= 60 for delay in delays)


def test_one_run_is_delayed_the_same_way_every_time_it_is_asked_for() -> None:
    time = at("2026-01-01T10:00:00+00:00")
    first = JitterTrigger(CallbackTrigger(lambda _run: time, "fixed"), key="task")
    second = JitterTrigger(CallbackTrigger(lambda _run: time, "fixed"), key="task")

    runs = {trigger.get_next_run_date(time - timedelta(seconds=61)) for trigger in (first, second)}

    assert len(runs) == 1


def test_different_keys_spread_tasks_sharing_a_trigger() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    runs = {
        JitterTrigger(PeriodicalTrigger(60, start), key=f"task-{n}").get_next_run_date(start)
        for n in range(20)
    }

    assert len(runs) > 1


def _delayed(run: datetime, named: str) -> datetime:
    """Where ``run`` of the trigger ``named`` lands with up to 60 seconds of jitter, keyed "task".

    A trigger yielding that one run, under the same name and key, delays it
    the way the named one does: a delay depends on nothing else.
    """
    only = CallbackTrigger(lambda after: run if after < run else None, named)
    delayed = JitterTrigger(only, 60, key="task").get_next_run_date(run - timedelta(seconds=61))
    assert delayed is not None
    return delayed


def test_no_run_is_lost_when_the_jitter_is_longer_than_the_interval() -> None:
    start = at("2026-07-07T16:30:00+00:00")
    every_ten = PeriodicalTrigger(10, start)
    trigger = JitterTrigger(every_ten, 60, key="task")
    low, high = start + timedelta(seconds=660), start + timedelta(seconds=1500)
    # Only runs from after start + 600 s can land after start + 660 s.
    undelayed = (start + timedelta(seconds=600 + 10 * n) for n in range(1, 91))
    expected = sorted(
        {delayed for run in undelayed if low < (delayed := _delayed(run, str(every_ten))) <= high}
    )

    seen: list[datetime] = []
    run: datetime | None = start
    while run is not None and run <= high:
        if run > low:
            seen.append(run)
        run = trigger.get_next_run_date(run)

    assert seen == expected


def test_the_delay_comes_from_the_random_source_given() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    first = JitterTrigger(PeriodicalTrigger(60, start), random_source=random.Random(7))
    second = JitterTrigger(PeriodicalTrigger(60, start), random_source=random.Random(7))

    assert first.get_next_run_date(start) == second.get_next_run_date(start)


def test_runs_do_not_drift_by_the_delays() -> None:
    start = at("2026-01-01T00:00:00+00:00")
    trigger = JitterTrigger(PeriodicalTrigger(60, start), 30)
    run = start + timedelta(seconds=30)  # past where the run at start lands
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
    trigger = JitterTrigger(PeriodicalTrigger(20), 15)

    assert str(trigger) == "every 20 seconds with 0-15 second jitter"


def test_a_bound_that_is_not_positive_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="max_seconds"):
        _ = JitterTrigger(PeriodicalTrigger(20), 0)


def _nightly() -> CronExpressionTrigger:
    return CronExpressionTrigger.from_expression("0 3 * * *", timezone="Europe/Bucharest")


def _walk(trigger: CronExpressionTrigger | JitterTrigger, start: datetime) -> list[datetime]:
    """Return the trigger's next runs from ``start``, each asked from the one before, in UTC."""
    runs: list[datetime] = []
    run = start
    for _ in range(_NIGHTS):
        next_run = trigger.get_next_run_date(run)
        assert next_run is not None
        runs.append(next_run.astimezone(UTC))
        run = next_run
    return runs


@pytest.mark.parametrize("start", _CLOCK_CHANGES.values(), ids=_CLOCK_CHANGES.keys())
@pytest.mark.parametrize("max_seconds", [1, 30, 59, 600])
@pytest.mark.parametrize("key", ["", "purge", "report"])
def test_jittered_runs_keep_moving_forward_across_a_clock_change(
    start: datetime, max_seconds: int, key: str
) -> None:
    # The key seeds every delay, so each one draws a different set of them.
    undelayed = _walk(_nightly(), start)

    runs = _walk(JitterTrigger(_nightly(), max_seconds, key=key), start)

    assert all(earlier < later for earlier, later in pairwise(runs))
    assert all(
        base <= run <= base + timedelta(seconds=max_seconds)
        for base, run in zip(undelayed, runs, strict=True)
    )


def test_the_second_three_oclock_of_the_night_the_clocks_go_back_is_a_run_of_its_own() -> None:
    jittered = JitterTrigger(_nightly(), 59)
    first = jittered.get_next_run_date(datetime(2026, 10, 25, 2, 59, tzinfo=_BUCHAREST))
    assert first is not None

    second = jittered.get_next_run_date(first)

    assert second is not None
    repeated = datetime(2026, 10, 25, 1, tzinfo=UTC)  # 03:00 the second time, at +02:00
    assert repeated <= second.astimezone(UTC) <= repeated + timedelta(seconds=59)
