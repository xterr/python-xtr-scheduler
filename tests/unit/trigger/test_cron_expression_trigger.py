"""Runs when a cron expression matches."""

from __future__ import annotations

import re
from datetime import datetime, tzinfo
from itertools import pairwise
from typing import final
from zoneinfo import ZoneInfo

import pytest
from typing_extensions import override

from tests.support.dates import at
from xtr_scheduler.exception import InvalidArgumentError, SchedulerLogicError
from xtr_scheduler.trigger import CronExpressionInterface, CronExpressionTrigger


@pytest.mark.parametrize(
    ("hashed", "picked"),
    [
        ("# * * * *", "43 * * * *"),
        ("# # * * *", "43 12 * * *"),
        ("# # # # #", "43 12 10 5 0"),
        ("# # 1,15 * *", "43 12 1,15 * *"),
        ("#hourly", "43 * * * *"),
        ("#daily", "43 12 * * *"),
        ("#weekly", "43 12 * * 2"),
        ("#midnight", "43 1 * * *"),
        ("#(1-15) * # * #(3-5)", "11 * 13 * 4"),
    ],
)
def test_a_hashed_expression_picks_the_same_values_for_the_same_context(
    hashed: str, picked: str
) -> None:
    """Pinned: a pick that changed between releases would move every hashed run."""
    first = CronExpressionTrigger.from_expression(hashed, "my task")
    again = CronExpressionTrigger.from_expression(hashed, "my task")
    other = CronExpressionTrigger.from_expression(hashed, "another task")

    assert str(first) == picked
    assert str(again) == picked
    assert str(other) != picked


def test_each_hashed_field_is_picked_on_its_own() -> None:
    fields = str(CronExpressionTrigger.from_expression("#(1-6) #(1-6) #(1-6) #(1-6) #(1-6)", "ctx"))

    assert len(set(fields.split())) > 1


@pytest.mark.parametrize("context", [f"task {n}" for n in range(200)])
def test_a_hashed_day_of_month_is_one_every_month_has(context: str) -> None:
    day = int(str(CronExpressionTrigger.from_expression("# # # * *", context)).split()[2])

    assert 1 <= day <= 28


def test_a_hashed_expression_needs_a_context() -> None:
    with pytest.raises(SchedulerLogicError, match="context must be provided"):
        _ = CronExpressionTrigger.from_expression("# * * * *")


def test_an_expression_without_hashing_is_kept_as_written() -> None:
    assert (
        str(CronExpressionTrigger.from_expression("56 20 1 9 0", "some context")) == "56 20 1 9 0"
    )
    assert str(CronExpressionTrigger.from_expression("@daily")) == "@daily"


def test_the_nth_weekday_is_not_hashing_and_needs_no_context() -> None:
    trigger = CronExpressionTrigger.from_expression("0 9 * * 5#3")

    assert trigger.get_next_run_date(at("2026-09-01T00:00:00+00:00")) == at(
        "2026-09-18T09:00:00+00:00"
    )


@pytest.mark.parametrize(
    ("expression", "hashed"),
    [("# * * * *", True), ("#daily", True), ("0 9 * * 5#3", False), ("* * * * *", False)],
)
def test_it_tells_a_hashed_expression_apart(expression: str, hashed: bool) -> None:
    assert CronExpressionTrigger.is_hashed(expression) is hashed


def test_an_invalid_expression_is_refused_where_it_is_declared() -> None:
    with pytest.raises(
        InvalidArgumentError, match=re.escape('Invalid cron expression "61 * * * *"')
    ):
        _ = CronExpressionTrigger.from_expression("61 * * * *")


def test_the_next_run_is_strictly_after_one_that_matches() -> None:
    trigger = CronExpressionTrigger.from_expression("*/5 * * * *")

    assert trigger.get_next_run_date(at("2026-01-01T10:00:00+00:00")) == at(
        "2026-01-01T10:05:00+00:00"
    )
    assert trigger.get_next_run_date(at("2026-01-01T10:04:59.999999+00:00")) == at(
        "2026-01-01T10:05:00+00:00"
    )


def test_without_a_timezone_it_reads_the_clock_of_the_run() -> None:
    paris = ZoneInfo("Europe/Paris")
    trigger = CronExpressionTrigger.from_expression("0 12 * * *")

    next_run = trigger.get_next_run_date(datetime(2026, 1, 1, 8, tzinfo=paris))

    assert next_run == datetime(2026, 1, 1, 12, tzinfo=paris)
    assert next_run is not None
    assert next_run.tzinfo == paris


def test_a_timezone_given_is_the_clock_it_reads() -> None:
    trigger = CronExpressionTrigger.from_expression("0 12 * * *", timezone="UTC")

    next_run = trigger.get_next_run_date(datetime(2026, 1, 1, 8, tzinfo=ZoneInfo("Europe/Paris")))

    assert next_run == at("2026-01-01T12:00:00+00:00")


@pytest.mark.parametrize("timezone", ["Z", "+02:00"])
def test_a_timezone_is_read_as_the_clock_reads_one(timezone: str) -> None:
    trigger = CronExpressionTrigger.from_expression("0 12 * * *", timezone=timezone)

    next_run = trigger.get_next_run_date(at("2026-01-01T13:00:00+00:00"))

    assert next_run is not None
    assert (next_run.hour, next_run.minute) == (12, 0)


def test_an_unknown_timezone_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='timezone "Mars/Olympus" is not known'):
        _ = CronExpressionTrigger.from_expression("0 12 * * *", timezone="Mars/Olympus")


def test_a_time_skipped_by_a_clock_change_runs_at_the_first_time_that_exists() -> None:
    bucharest = ZoneInfo("Europe/Bucharest")
    trigger = CronExpressionTrigger.from_expression("30 3 * * *", timezone=bucharest)

    next_run = trigger.get_next_run_date(datetime(2026, 3, 29, 0, tzinfo=bucharest))

    assert next_run == datetime(2026, 3, 29, 4, tzinfo=bucharest)


def test_an_hour_repeated_by_a_clock_change_matches_each_time_it_comes() -> None:
    bucharest = ZoneInfo("Europe/Bucharest")
    trigger = CronExpressionTrigger.from_expression("0 * * * *", timezone=bucharest)
    run = datetime(2026, 10, 25, 3, tzinfo=bucharest)
    instants: list[float] = []
    for _ in range(3):
        next_run = trigger.get_next_run_date(run)
        assert next_run is not None
        instants.append(next_run.timestamp())
        run = next_run

    assert [b - a for a, b in pairwise(instants)] == [3600.0, 3600.0]


@final
class FixedExpression(CronExpressionInterface):
    """Any expression implementation: the trigger depends on the interface only."""

    @override
    def next_after(self, run: datetime, timezone: tzinfo, /) -> datetime:
        del run, timezone
        return at("2030-01-01T00:00:00+00:00")

    @override
    def __str__(self) -> str:
        return "fixed"


def test_any_cron_implementation_can_stand_behind_the_trigger() -> None:
    trigger = CronExpressionTrigger(FixedExpression())

    assert str(trigger) == "fixed"
    assert trigger.get_next_run_date(at("2026-01-01T00:00:00+00:00")) == at(
        "2030-01-01T00:00:00+00:00"
    )
