"""The declarations an application writes: schedules, and tasks run on them."""

from __future__ import annotations

from .as_cron_task import as_cron_task
from .as_periodic_task import as_periodic_task
from .as_schedule import as_schedule

__all__ = ["as_cron_task", "as_periodic_task", "as_schedule"]
