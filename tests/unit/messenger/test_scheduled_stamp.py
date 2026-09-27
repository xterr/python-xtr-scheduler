"""Marks a message as produced by a schedule, and for which run."""

from __future__ import annotations

from xtr_messenger import Envelope, JsonSerializer

from tests.support.contexts import a_context
from tests.support.messages import Named
from xtr_scheduler.messenger import ScheduledStamp
from xtr_scheduler.trigger import SerializedTrigger


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
    wire = JsonSerializer()

    decoded = wire.decode(wire.encode(Envelope(Named("x"), (stamp,))))

    assert decoded.last(ScheduledStamp) == stamp
