"""A cache pool whose saves, and reads, can be made to fail."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_cache import CacheItem
from xtr_cache_contracts import CacheMixin, ItemInterface


@final
class FlakyCache(CacheMixin):
    """Keeps values in a dict until told to fail.

    ``readonly`` still serves what was saved but saves nothing; ``dead``
    neither serves nor saves. ``save_results`` scripts the outcome of the next
    saves, one per save, before falling back to the mode.
    """

    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.failure: str | None = None
        self.save_results: list[bool] = []

    @override
    async def get_item(self, key: str, /) -> ItemInterface:
        if self.failure == "dead" or key not in self.values:
            return CacheItem(key)
        return CacheItem(key, self.values[key], hit=True)

    @override
    async def save(self, item: ItemInterface, /) -> bool:
        scripted = self.save_results.pop(0) if self.save_results else True
        if not scripted or self.failure is not None:
            return False
        self.values[item.key] = item.get()
        return True

    @override
    async def delete_item(self, key: str, /) -> bool:
        _ = self.values.pop(key, None)
        return True
