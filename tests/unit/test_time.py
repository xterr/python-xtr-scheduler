"""Reading dates the scheduler is given, and exact arithmetic on them."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.support.dates import at
from xtr_scheduler._time import add_months, aware, from_microseconds, microseconds
from xtr_scheduler.exception import InvalidArgumentError


def test_an_iso_string_or_an_aware_datetime_is_read() -> None:
    assert aware("2026-01-01T00:00:00+02:00", "date") == at("2026-01-01T00:00:00+02:00")
    assert aware(at("2026-01-01T00:00:00Z"), "date") == at("2026-01-01T00:00:00Z")


def test_a_date_without_a_zone_is_refused_naming_what_it_was() -> None:
    with pytest.raises(InvalidArgumentError, match="The start date 2026-01-01T00:00:00 has no"):
        _ = aware(datetime(2026, 1, 1), "start date")


def test_microseconds_round_trip_exactly() -> None:
    moment = at("2026-01-01T00:00:00.000001+00:00")

    assert from_microseconds(microseconds(moment), UTC) == moment


def test_adding_months_keeps_the_day_or_lands_on_the_month_s_last() -> None:
    assert add_months(at("2026-01-31T09:00:00+00:00"), 1) == at("2026-02-28T09:00:00+00:00")
    assert add_months(at("2026-11-15T09:00:00+00:00"), 3) == at("2027-02-15T09:00:00+00:00")
