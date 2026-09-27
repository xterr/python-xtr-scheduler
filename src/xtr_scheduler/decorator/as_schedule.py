"""Declare the provider of a schedule."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from xtr_scheduler.registry.declarations import declare_schedule

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

__all__ = ["as_schedule"]

ProviderT = TypeVar("ProviderT", bound="type[ScheduleProviderInterface]")


def as_schedule(name: str = "default") -> Callable[[ProviderT], ProviderT]:
    """Declare the decorated class as the provider of the schedule ``name``.

    For example::

        @as_schedule("reports")
        class ReportSchedule(ScheduleProviderInterface):
            def __init__(self, cache: CacheInterface) -> None:
                self._schedule = Schedule(...).stateful(cache)

            def get_schedule(self) -> Schedule:
                return self._schedule

    ``schedule://reports`` then serves it. A container builds the class with
    its dependencies; without one it is built with no arguments. Tasks
    declared on the same schedule join it. A kernel refuses two classes
    providing one schedule.
    """

    def declare(provider: ProviderT) -> ProviderT:
        declare_schedule(provider, name)
        return provider

    return declare
