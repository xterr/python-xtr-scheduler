"""The application's cache config: pools in memory."""

from __future__ import annotations

from xtr_cache.bundle import CacheConfig
from xtr_dependency_injection import configure


@configure
def cache() -> CacheConfig:
    """Keep every pool in memory; the scheduler adds its own on the same adapter."""
    return CacheConfig(app="array", stampede_lock=None)
