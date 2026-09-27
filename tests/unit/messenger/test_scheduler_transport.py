"""A transport that receives a schedule's messages as they fall due."""

from __future__ import annotations

from contextlib import aclosing

import pytest
from xtr_clock import MockClock
from xtr_messenger import Envelope, ReceivedStamp, RedispatchMessage, TransportNamesStamp

from tests.support.contexts import a_context
from tests.support.listed_generator import ListedGenerator
from tests.support.messages import Named
from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.messenger import ScheduledStamp, SchedulerTransport

pytestmark = pytest.mark.anyio


async def first(transport: SchedulerTransport, count: int) -> list[Envelope]:
    taken: list[Envelope] = []
    async with aclosing(transport.get()) as envelopes:
        async for envelope in envelopes:
            taken.append(envelope)
            if len(taken) == count:
                break
    return taken


async def test_each_message_arrives_stamped_with_its_run_and_received() -> None:
    context = a_context()
    transport = SchedulerTransport(
        ListedGenerator([(context, Named("a"))]), name="scheduler_default", clock=MockClock()
    )

    [envelope] = await first(transport, 1)

    assert envelope.message == Named("a")
    assert envelope.last(ScheduledStamp) == ScheduledStamp.from_context(context)
    assert envelope.last(ReceivedStamp) == ReceivedStamp("scheduler_default")


async def test_nothing_due_waits_a_poll_interval_on_the_clock_and_asks_again() -> None:
    clock = MockClock("2026-01-01T00:00:00+00:00")
    generator = ListedGenerator([], [], [(a_context(), Named("late"))])
    transport = SchedulerTransport(generator, clock=clock, poll_interval=5)

    [envelope] = await first(transport, 1)

    assert envelope.message == Named("late")
    assert generator.calls == 3
    assert clock.now().isoformat() == "2026-01-01T00:00:10+00:00"


async def test_a_redispatch_carries_the_stamp_on_the_envelope_it_sends_on() -> None:
    context = a_context()
    transport = SchedulerTransport(
        ListedGenerator([(context, RedispatchMessage(Named("a"), "urgent"))]), clock=MockClock()
    )

    [envelope] = await first(transport, 1)

    redispatch = envelope.message
    assert isinstance(redispatch, RedispatchMessage)
    assert redispatch.transport_names == ("urgent",)
    inner = redispatch.envelope
    assert isinstance(inner, Envelope)
    assert inner.message == Named("a")
    assert inner.last(ScheduledStamp) == ScheduledStamp.from_context(context)
    assert inner.last(TransportNamesStamp) is None


async def test_with_messenger_routing_every_message_is_sent_on() -> None:
    transport = SchedulerTransport(
        ListedGenerator([(a_context(), Named("a"))]),
        use_messenger_routing=True,
        clock=MockClock(),
    )

    [envelope] = await first(transport, 1)

    redispatch = envelope.message
    assert isinstance(redispatch, RedispatchMessage)
    assert redispatch.transport_names == ()
    assert redispatch.message == Named("a")


async def test_settling_does_nothing_and_sending_is_refused() -> None:
    transport = SchedulerTransport(ListedGenerator(), clock=MockClock())
    envelope = Envelope(Named("a"))

    await transport.ack(envelope)
    await transport.reject(envelope)

    with pytest.raises(SchedulerLogicError, match="cannot send messages"):
        _ = await transport.send(envelope)


async def test_when_the_worker_stops_asking_the_schedule_is_handed_back() -> None:
    generator = ListedGenerator([(a_context(), Named("a"))])
    transport = SchedulerTransport(generator, clock=MockClock())

    _ = await first(transport, 1)

    assert generator.closed
