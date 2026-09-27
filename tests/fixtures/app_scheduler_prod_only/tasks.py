"""A task that exists only in production."""

from __future__ import annotations

from xtr_scheduler.decorator import as_periodic_task


@as_periodic_task(60, schedule="nightly", env="prod")
def reconcile() -> None:
    """Never runs outside production."""
