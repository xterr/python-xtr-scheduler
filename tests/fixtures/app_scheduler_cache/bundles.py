"""The application's root bundles: the scheduler and the cache."""

from __future__ import annotations

from xtr_cache.bundle import CacheBundle

from xtr_scheduler.bundle import SchedulerBundle

BUNDLES = {CacheBundle: {"all": True}, SchedulerBundle: {"all": True}}
