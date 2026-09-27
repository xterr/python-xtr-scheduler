"""The xtr-dependency-injection bundle for xtr-scheduler."""

from __future__ import annotations

from .scheduler_bundle import SCHEDULER_POOL, SchedulerBundle
from .scheduler_config import SchedulerConfig

__all__ = ["SCHEDULER_POOL", "SchedulerBundle", "SchedulerConfig"]
