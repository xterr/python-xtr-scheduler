"""Reading dates the scheduler is given, and exact arithmetic on them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.support.dates import at
from xtr_scheduler._time import aware, from_microseconds, microseconds, seconds_between, shifted
from xtr_scheduler.exception import InvalidArgumentError

_BUCHAREST = ZoneInfo("Europe/Bucharest")


def test_an_iso_string_or_an_aware_datetime_is_read() -> None:
    assert aware("2026-01-01T00:00:00+02:00", "date") == at("2026-01-01T00:00:00+02:00")
    assert aware(at("2026-01-01T00:00:00Z"), "date") == at("2026-01-01T00:00:00Z")


def test_a_date_without_a_zone_is_refused_naming_what_it_was() -> None:
    with pytest.raises(InvalidArgumentError, match="The start date 2026-01-01T00:00:00 has no"):
        _ = aware(datetime(2026, 1, 1), "start date")


def test_microseconds_round_trip_exactly() -> None:
    moment = at("2026-01-01T00:00:00.000001+00:00")

    assert from_microseconds(microseconds(moment), UTC) == moment


def test_a_shift_into_the_second_pass_of_a_repeated_hour_lands_there() -> None:
    # 03:59:30 the first time Bucharest lives through it on 2026-10-25, then a minute.
    first_pass = datetime(2026, 10, 25, 3, 59, 30, tzinfo=_BUCHAREST)

    moved = shifted(first_pass, timedelta(minutes=1))

    assert (moved.replace(tzinfo=None), moved.fold, moved.tzinfo) == (
        datetime(2026, 10, 25, 3, 0, 30),
        1,
        _BUCHAREST,
    )


def test_the_seconds_between_the_two_passes_of_a_repeated_hour_are_an_hour() -> None:
    first_pass = datetime(2026, 10, 25, 3, 15, tzinfo=_BUCHAREST)
    second_pass = first_pass.replace(fold=1)

    assert seconds_between(first_pass, second_pass) == 3600.0
