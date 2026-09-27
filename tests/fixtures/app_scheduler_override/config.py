"""The application's messenger config: its own ``scheduler_default``, routing on."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig

from .schedule import Tock


@configure
def messenger() -> MessageBusConfig:
    """Route what the schedule sends to an in-memory queue instead of handling it."""
    return MessageBusConfig(
        transports={
            "scheduler_default": TransportConfig("schedule://default?use_messenger_routing=true"),
            "tocks": TransportConfig("in-memory://"),
        },
        routing={Tock: "tocks"},
    )
