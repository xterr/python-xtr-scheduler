"""Marks a message as produced by a schedule, and for which run."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from xtr_messenger import Envelope, JsonSerializer
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.support.contexts import a_context
from tests.support.messages import Named
from xtr_scheduler.messenger import ScheduledStamp
from xtr_scheduler.trigger import CronExpressionTrigger, SerializedTrigger

_NIGHTLY = CronExpressionTrigger.from_expression("0 3 * * *", None, "Europe/Bucharest")


def _nightly_runs() -> list[tuple[datetime, datetime | None]]:
    """Return the three nightly runs around the clocks going back, each with the run after it.

    The night before the change, whose next run falls in the repeated hour, then that hour's
    first and second 03:00.
    """
    run = _NIGHTLY.get_next_run_date(datetime(2026, 10, 23, 12, tzinfo=UTC))
    runs: list[tuple[datetime, datetime | None]] = []
    while run is not None and len(runs) < 3:
        following = _NIGHTLY.get_next_run_date(run)
        runs.append((run, following))
        run = following
    return runs


def test_it_records_the_run_with_the_trigger_s_description() -> None:
    context = a_context()

    stamp = ScheduledStamp.from_context(context)

    assert (stamp.name, stamp.id, stamp.trigger) == ("default", "abc", "every minute")
    assert (stamp.triggered_at, stamp.next_trigger_at) == (
        context.triggered_at,
        context.next_trigger_at,
    )


def test_its_context_carries_a_stand_in_trigger() -> None:
    context = ScheduledStamp.from_context(a_context()).message_context

    assert isinstance(context.trigger, SerializedTrigger)
    assert str(context.trigger) == "every minute"
    assert context.triggered_at == a_context().triggered_at


def test_it_survives_a_transport() -> None:
    stamp = ScheduledStamp.from_context(a_context())
    wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))

    decoded = wire.decode(wire.encode(Envelope(Named("x"), (stamp,))))

    assert decoded.last(ScheduledStamp) == stamp


@pytest.mark.parametrize(("run", "following"), _nightly_runs(), ids=["eve", "first", "second"])
def test_it_keeps_the_zone_and_fold_of_a_run_around_a_clock_change(
    run: datetime, following: datetime | None
) -> None:
    stamp = ScheduledStamp("default", "abc", str(_NIGHTLY), run, following)
    wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))

    decoded = wire.decode(wire.encode(Envelope(Named("x"), (stamp,)))).last(ScheduledStamp)

    assert decoded == stamp
    assert decoded is not None
    assert decoded.next_trigger_at is not None
    assert following is not None
    assert (decoded.triggered_at.tzinfo, decoded.triggered_at.fold) == (run.tzinfo, run.fold)
    assert (decoded.next_trigger_at.tzinfo, decoded.next_trigger_at.fold) == (
        following.tzinfo,
        following.fold,
    )
