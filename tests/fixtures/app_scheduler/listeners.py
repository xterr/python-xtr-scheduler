"""Stops the worker once enough has run."""

from __future__ import annotations

from xtr_dependency_injection import Injected
from xtr_event_dispatcher import as_event_listener
from xtr_messenger.event import WorkerRunningEvent

from .services import Journal

#: How many entries end a test run.
ENOUGH = 6


@as_event_listener()
def stop_when_done(event: WorkerRunningEvent, journal: Injected[Journal]) -> None:
    """Stop the worker once the journal has enough entries."""
    if len(journal.entries) >= ENOUGH:
        event.worker.stop()
