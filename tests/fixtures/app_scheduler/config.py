"""The application's messenger config: no transport for the schedule — the bundle adds it."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig


@configure
def messenger() -> MessageBusConfig:
    """Configure one unrelated queue; ``scheduler_default`` is registered by the bundle."""
    return MessageBusConfig(transports={"jobs": TransportConfig("in-memory://")})
