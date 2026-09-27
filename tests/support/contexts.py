"""A message context for tests that only need one to exist."""

from __future__ import annotations

from tests.support.dates import at
from xtr_scheduler.generator import MessageContext
from xtr_scheduler.trigger import SerializedTrigger


def a_context(name: str = "default") -> MessageContext:
    """Return a context for a run of schedule ``name``."""
    return MessageContext(
        name=name,
        id="abc",
        trigger=SerializedTrigger("every minute"),
        triggered_at=at("2026-01-01T00:00:00+00:00"),
        next_trigger_at=at("2026-01-01T00:01:00+00:00"),
    )
