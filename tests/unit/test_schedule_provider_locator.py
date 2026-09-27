"""Schedule providers by name."""

from __future__ import annotations

import pytest

from xtr_scheduler import Schedule
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

pytestmark = pytest.mark.anyio


async def test_it_hands_over_providers_by_schedule_name_in_order() -> None:
    first, second = Schedule(), Schedule()
    locator = ScheduleProviderLocator({"default": first, "reports": second})

    assert await locator.get("reports") is second
    assert locator.names() == ("default", "reports")
    assert locator.has("default")
    assert not locator.has("nope")


async def test_it_wraps_another_locator() -> None:
    schedule = Schedule()

    assert (
        await ScheduleProviderLocator(ScheduleProviderLocator({"a": schedule})).get("a") is schedule
    )


async def test_an_unknown_schedule_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='The schedule "nope" is not found'):
        _ = await ScheduleProviderLocator({}).get("nope")
