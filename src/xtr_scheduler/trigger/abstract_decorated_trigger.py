"""A trigger that changes what another trigger answers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .stateful_trigger_interface import StatefulTriggerInterface

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime

    from .trigger_interface import TriggerInterface

__all__ = ["AbstractDecoratedTrigger"]


class AbstractDecoratedTrigger(StatefulTriggerInterface, ABC):
    """Wraps another trigger, which stays reachable for describing the schedule.

    Passes the schedule's starting point on to the wrapped trigger, so a
    decorated "every hour" is anchored the same way an undecorated one is.
    """

    def __init__(self, inner: TriggerInterface) -> None:
        """Decorate ``inner``."""
        self._inner: TriggerInterface = inner

    @abstractmethod
    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None: ...

    @abstractmethod
    @override
    def __str__(self) -> str: ...

    @override
    def continue_(self, started_at: datetime, /) -> None:
        if isinstance(self._inner, StatefulTriggerInterface):
            self._inner.continue_(started_at)

    @property
    def decorated(self) -> TriggerInterface:
        """Return the trigger this one wraps directly."""
        return self._inner

    @final
    def inner(self) -> TriggerInterface:
        """Return the trigger at the bottom of the decorations."""
        inner = self._inner
        while isinstance(inner, AbstractDecoratedTrigger):
            inner = inner.decorated
        return inner

    @final
    def decorators(self) -> Iterator[AbstractDecoratedTrigger]:
        """Yield this decoration, then every one beneath it, outermost first."""
        yield self
        inner = self._inner
        while isinstance(inner, AbstractDecoratedTrigger):
            yield inner
            inner = inner.decorated
