"""Asks for a method of a scheduled task to be called."""

from __future__ import annotations

from xtr_messenger import Envelope, JsonSerializer

from xtr_scheduler.messenger import ServiceCallMessage


def test_it_describes_the_call() -> None:
    assert str(ServiceCallMessage("app.Reports")) == "@app.Reports"
    assert str(ServiceCallMessage("app.Reports", "nightly")) == "@app.Reports::nightly"


def test_it_crosses_a_transport() -> None:
    message = ServiceCallMessage("app.Reports", "nightly", ("eu", 3))
    wire = JsonSerializer()

    assert wire.decode(wire.encode(Envelope(message))).message == message
