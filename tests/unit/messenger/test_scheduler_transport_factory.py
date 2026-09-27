"""Builds ``schedule://<name>`` transports."""

from __future__ import annotations

import re
from contextlib import aclosing

import pytest
from xtr_clock import MockClock
from xtr_messenger import Dsn, Envelope, RedispatchMessage, TransportConfig
from xtr_messenger.exception import UnknownTransportOptionError

from tests.support.messages import Named
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.messenger import SchedulerTransport, SchedulerTransportFactory

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


def schedule() -> Schedule:
    return Schedule(RecurringMessage.every(60, Named("tick"), from_=START))


def test_it_serves_the_schedule_scheme_only() -> None:
    factory = SchedulerTransportFactory({})

    assert factory.supports(Dsn.parse("schedule://default"))
    assert not factory.supports(Dsn.parse("in-memory://"))


async def test_it_builds_a_transport_for_the_schedule_the_dsn_names() -> None:
    clock = MockClock(START)
    factory = SchedulerTransportFactory({"default": schedule()}, clock=clock)

    built = factory.create({"scheduler_default": TransportConfig("schedule://default")})

    transport = built["scheduler_default"]
    assert isinstance(transport, SchedulerTransport)
    async with aclosing(transport.get()) as envelopes:
        first = await anext(envelopes)
    assert first.message == Named("tick")


def test_a_dsn_without_a_name_is_refused() -> None:
    factory = SchedulerTransportFactory({"default": schedule()})

    with pytest.raises(
        InvalidArgumentError, match=re.escape('must contain a name, e.g. "schedule://default"')
    ):
        _ = factory.create({"t": TransportConfig("schedule://")})


def test_a_schedule_that_does_not_exist_is_refused() -> None:
    factory = SchedulerTransportFactory({"default": schedule()})

    with pytest.raises(InvalidArgumentError, match='The schedule "reports" is not found'):
        _ = factory.create({"t": TransportConfig("schedule://reports")})


def test_an_unknown_setting_is_refused() -> None:
    factory = SchedulerTransportFactory({"default": schedule()})

    with pytest.raises(UnknownTransportOptionError):
        _ = factory.create({"t": TransportConfig("schedule://default?speed=fast")})


async def test_messenger_routing_is_switched_on_by_the_dsn() -> None:
    factory = SchedulerTransportFactory({"default": schedule()}, clock=MockClock(START))

    built = factory.create({"t": TransportConfig("schedule://default?use_messenger_routing=true")})

    transport = built["t"]
    assert isinstance(transport, SchedulerTransport)
    async with aclosing(transport.get()) as envelopes:
        first: Envelope = await anext(envelopes)
    assert isinstance(first.message, RedispatchMessage)
