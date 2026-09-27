"""Skips another trigger's runs that fall in a window."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler._time import aware

from .abstract_decorated_trigger import AbstractDecoratedTrigger

if TYPE_CHECKING:
    from datetime import datetime

    from .trigger_interface import TriggerInterface

__all__ = ["ExcludeTimeTrigger"]


@final
class ExcludeTimeTrigger(AbstractDecoratedTrigger):
    """Skips runs of another trigger from ``from_`` to ``until``, both included.

    A run that falls in the window is replaced by the first run after it —
    a single step, so a window longer than the interval still lets one run
    through at its end.
    """

    def __init__(
        self,
        inner: TriggerInterface,
        from_: datetime | str,
        until: datetime | str,
    ) -> None:
        """Skip ``inner``'s runs from ``from_`` to ``until``.

        Raises:
            InvalidArgumentError: If a date has no timezone.
        """
        super().__init__(inner)
        self._from = aware(from_, "start date")
        self._until = aware(until, "end date")

    @override
    def __str__(self) -> str:
        return (
            f"{self._inner}, excluding from {self._from.isoformat(timespec='seconds')} "
            f"until {self._until.isoformat(timespec='seconds')}"
        )

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        next_run = self._inner.get_next_run_date(run)
        if next_run is not None and self._from <= next_run <= self._until:
            return self._inner.get_next_run_date(self._until)
        return next_run
