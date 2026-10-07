"""Runs at a fixed interval."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.support.dates import at
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger import PeriodicalTrigger

_FROM = "2022-02-22T13:34:00+01:00"


@pytest.mark.parametrize(
    "interval",
    [
        86400,
        "86400",
        "1 day",
        "24 hours",
        "1440 minutes",
        "86400 seconds",
        "1day",
        "24hours",
        "1440minutes",
        "86400seconds",
        "P1D",
        "PT24H",
        "PT1440M",
        "PT86400S",
        timedelta(days=1),
    ],
)
def test_every_way_of_saying_a_day_lands_on_the_same_run(
    interval: int | str | timedelta,
) -> None:
    trigger = PeriodicalTrigger(interval, _FROM)

    next_run = trigger.get_next_run_date(at("2922-02-22T12:34:00+00:00"))

    assert next_run == at("2922-02-23T13:34:00+01:00")
    assert next_run is not None
    assert next_run.utcoffset() == timedelta(hours=1)


@pytest.mark.parametrize(
    "interval",
    ["wrong", "3600.5", "-3600", "4 minutes 20 seconds", "P", "PT", "P1H"],
)
def test_an_interval_it_cannot_read_is_refused(interval: str) -> None:
    with pytest.raises(InvalidArgumentError, match="Invalid interval"):
        _ = PeriodicalTrigger(interval, _FROM)


@pytest.mark.parametrize(
    "interval",
    [-3600, "0", 0, "PT0S", "P0D", "0 seconds", "0 days", timedelta(0), 0.0000001],
)
def test_an_interval_that_is_not_positive_is_refused(interval: int | str | timedelta) -> None:
    with pytest.raises(InvalidArgumentError, match="must be greater than zero"):
        _ = PeriodicalTrigger(interval, _FROM)


def test_a_boolean_is_not_a_number_of_seconds() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PeriodicalTrigger(True, _FROM)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        (20, "every 20 seconds"),
        ("20", "every 20 seconds"),
        ("PT2S", "every 2 seconds (PT2S)"),
        ("20 seconds", "every 20 seconds"),
        ("2 hours", "every 2 hours"),
        (timedelta(seconds=2), "every 2 seconds"),
        (timedelta(milliseconds=1500), "every 1.5 seconds"),
        (1.5, "every 1.5 seconds"),
    ],
)
def test_it_describes_itself(interval: int | str | timedelta, expected: str) -> None:
    assert str(PeriodicalTrigger(interval)) == expected


def test_it_describes_the_bounds_it_was_given() -> None:
    trigger = PeriodicalTrigger("1 hour", _FROM, "2026-06-01T00:00:00+00:00")

    assert str(trigger) == (
        "every 1 hour from 2022-02-22T13:34:00+01:00 until 2026-06-01T00:00:00+00:00"
    )


def test_two_windows_of_one_interval_describe_themselves_apart() -> None:
    first = PeriodicalTrigger("1 hour", until="2026-06-01T00:00:00+00:00")
    second = PeriodicalTrigger("1 hour", until="2027-06-01T00:00:00+00:00")

    assert str(first) != str(second)


def test_a_fractional_number_of_seconds_is_kept() -> None:
    trigger = PeriodicalTrigger(1.5, "2026-01-01T00:00:00+00:00")

    assert trigger.get_next_run_date(at("2026-01-01T00:00:00+00:00")) == at(
        "2026-01-01T00:00:01.500000+00:00"
    )


def test_a_run_date_without_a_timezone_is_refused_as_the_package_refuses_dates() -> None:
    with pytest.raises(InvalidArgumentError, match="has no timezone"):
        _ = PeriodicalTrigger(60).get_next_run_date(datetime(2026, 1, 1))


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ("1970-01-01T00:00:00+00:00", "2020-02-20T02:00:00+02:00"),
        ("2020-02-20T01:40:00+02:00", "2020-02-20T02:00:00+02:00"),
        ("2020-02-20T01:59:00+02:00", "2020-02-20T02:00:00+02:00"),
        ("2020-02-20T02:00:00+02:00", "2020-02-20T02:10:00+02:00"),
        ("2020-02-20T02:05:00+02:00", "2020-02-20T02:10:00+02:00"),
        ("2020-02-20T02:49:59.999999+02:00", "2020-02-20T02:50:00+02:00"),
        ("2020-02-20T02:50:00+02:00", None),
        ("2020-02-20T03:00:00+02:00", None),
    ],
)
def test_runs_fall_on_the_interval_from_the_start_until_the_end(
    run: str, expected: str | None
) -> None:
    trigger = PeriodicalTrigger(600, "2020-02-20T02:00:00+02:00", "2020-02-20T03:00:00+02:00")

    next_run = trigger.get_next_run_date(at(run))

    assert next_run == (None if expected is None else at(expected))


def test_the_end_is_exclusive_to_the_microsecond() -> None:
    trigger = PeriodicalTrigger(600, "2020-02-20T02:00:00Z", "2020-02-20T03:01:00Z")

    assert trigger.get_next_run_date(at("2020-02-20T02:59:59.999999Z")) == at(
        "2020-02-20T03:00:00Z"
    )
    assert trigger.get_next_run_date(at("2020-02-20T03:00:00Z")) is None


def test_no_run_at_or_after_the_end_even_when_the_start_is_still_ahead() -> None:
    trigger = PeriodicalTrigger(3600, "2020-06-01T10:00:00Z", "2020-06-01T09:00:00Z")

    assert trigger.get_next_run_date(at("2020-06-01T08:00:00Z")) is None


def test_without_a_start_the_first_run_it_is_asked_about_anchors_it() -> None:
    trigger = PeriodicalTrigger(60)

    assert trigger.get_next_run_date(at("2026-01-01T10:00:30+00:00")) == at(
        "2026-01-01T10:01:30+00:00"
    )
    assert trigger.get_next_run_date(at("2026-01-01T10:05:00+00:00")) == at(
        "2026-01-01T10:05:30+00:00"
    )


def test_continue_anchors_a_trigger_given_no_start() -> None:
    trigger = PeriodicalTrigger(60)
    trigger.continue_(at("2026-01-01T10:00:10+00:00"))

    assert trigger.get_next_run_date(at("2026-01-01T10:05:00+00:00")) == at(
        "2026-01-01T10:05:10+00:00"
    )


def test_continue_leaves_an_explicit_start_alone() -> None:
    trigger = PeriodicalTrigger(60, "2026-01-01T10:00:00+00:00")
    trigger.continue_(at("2026-01-01T10:00:10+00:00"))

    assert trigger.get_next_run_date(at("2026-01-01T10:05:00+00:00")) == at(
        "2026-01-01T10:06:00+00:00"
    )


def test_every_day_keeps_its_wall_clock_time_across_a_clock_change() -> None:
    start = datetime(2026, 3, 28, 9, tzinfo=ZoneInfo("Europe/Bucharest"))
    daily = PeriodicalTrigger("1 day", start)

    first = daily.get_next_run_date(start)
    assert first is not None
    second = daily.get_next_run_date(first)
    assert second is not None

    assert (first.day, first.hour, first.utcoffset()) == (29, 9, timedelta(hours=3))
    assert (second.day, second.hour) == (30, 9)
    assert first.timestamp() - start.timestamp() == 23 * 3600


def test_every_month_from_the_31st_lands_on_the_last_day_of_shorter_months() -> None:
    trigger = PeriodicalTrigger("1 month", "2026-01-31T12:00:00+00:00")
    runs: list[str] = []
    run = at("2026-01-31T12:00:00+00:00")
    for _ in range(4):
        next_run = trigger.get_next_run_date(run)
        assert next_run is not None
        runs.append(next_run.date().isoformat())
        run = next_run

    assert runs == ["2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"]


def test_a_calendar_interval_stops_before_its_end() -> None:
    trigger = PeriodicalTrigger("1 week", "2026-01-01T00:00:00+00:00", "2026-01-15T00:00:00+00:00")

    assert trigger.get_next_run_date(at("2026-01-01T00:00:00+00:00")) == at(
        "2026-01-08T00:00:00+00:00"
    )
    assert trigger.get_next_run_date(at("2026-01-08T00:00:00+00:00")) is None


def test_the_next_run_is_strictly_after_the_one_asked_about() -> None:
    trigger = PeriodicalTrigger(7, "2026-01-01T00:00:00+00:00")
    run = at("2026-01-01T00:00:00+00:00")

    for _ in range(50):
        next_run = trigger.get_next_run_date(run)
        assert next_run is not None
        assert next_run - run == timedelta(seconds=7)
        run = next_run


def test_dates_are_accepted_as_iso_strings_or_datetimes_with_a_zone() -> None:
    trigger = PeriodicalTrigger(60, at("2026-01-01T00:00:00+00:00"))

    assert trigger.get_next_run_date(at("2026-01-01T00:00:00+00:00")) is not None


def test_a_date_without_a_zone_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="has no timezone"):
        _ = PeriodicalTrigger(60, "2026-01-01T00:00:00")


def test_a_date_that_is_not_iso_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="not an ISO 8601 date"):
        _ = PeriodicalTrigger(60, until="next tuesday")


def test_the_default_end_is_far_away_in_utc() -> None:
    trigger = PeriodicalTrigger(60, "2999-12-31T23:59:30+00:00")

    assert trigger.get_next_run_date(at("2999-12-31T23:59:30+00:00")) is None


def test_a_daily_run_at_a_skipped_hour_is_labelled_with_the_hour_that_replaced_it() -> None:
    start = datetime(2026, 3, 27, 3, 30, tzinfo=ZoneInfo("Europe/Bucharest"))
    daily = PeriodicalTrigger("1 day", start)

    first = daily.get_next_run_date(start)
    assert first is not None
    skipped = daily.get_next_run_date(first)

    assert skipped is not None
    assert skipped.isoformat() == "2026-03-29T04:30:00+03:00"


def test_a_start_in_the_repeated_hour_is_the_second_pass_not_the_first() -> None:
    """Europe/Bucharest repeats 03:00-04:00 on 2026-10-25; fold=1 is the later instant.

    A start anchored to the second pass (fold=1, the lower offset) must not be
    answered with the first-pass instant: the two share a wall clock but are an
    hour apart, and comparing them on the zone's wall clock — which ignores
    fold — would pick the earlier one.
    """
    bucharest = ZoneInfo("Europe/Bucharest")
    start = datetime(2026, 10, 25, 3, 30, tzinfo=bucharest, fold=1)
    trigger = PeriodicalTrigger(600, start, datetime(2026, 10, 25, 6, tzinfo=bucharest))

    first_run = trigger.get_next_run_date(datetime(2026, 10, 25, 3, 20, tzinfo=bucharest))

    assert first_run is not None
    assert first_run.timestamp() == start.timestamp()
    assert first_run.utcoffset() == timedelta(hours=2)
