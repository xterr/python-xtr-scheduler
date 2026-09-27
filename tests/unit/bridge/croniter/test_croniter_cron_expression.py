"""A cron expression read by croniter."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import DatePoint

from tests.support.dates import at
from xtr_scheduler.bridge.croniter import CroniterCronExpression
from xtr_scheduler.exception import InvalidArgumentError


def test_it_finds_the_first_match_after_a_run_on_the_zone_s_clock() -> None:
    expression = CroniterCronExpression("0 9 * * *")

    found = expression.next_after(at("2026-01-01T12:00:00+00:00"), ZoneInfo("Europe/Bucharest"))

    assert found == at("2026-01-02T09:00:00+02:00")


def test_it_accepts_aliases_and_the_nth_weekday() -> None:
    assert CroniterCronExpression("@hourly").next_after(at("2026-01-01T12:30:00+00:00"), UTC) == at(
        "2026-01-01T13:00:00+00:00"
    )
    assert str(CroniterCronExpression("0 0 * * 1#2")) == "0 0 * * 1#2"


@pytest.mark.parametrize("expression", ["", "61 * * * *", "* * *", "not cron"])
def test_an_invalid_expression_is_refused_when_built(expression: str) -> None:
    with pytest.raises(InvalidArgumentError, match="Invalid cron expression"):
        _ = CroniterCronExpression(expression)


def test_a_clock_date_point_is_read_like_any_datetime() -> None:
    run = DatePoint.parse("2026-01-01T12:30:00+00:00")

    found = CroniterCronExpression("0 * * * *").next_after(run, UTC)

    assert found == at("2026-01-01T13:00:00+00:00")
    assert type(found) is datetime
