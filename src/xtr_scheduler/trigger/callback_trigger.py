"""Runs whenever a function says."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .trigger_interface import TriggerInterface

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

__all__ = ["CallbackTrigger"]


@final
class CallbackTrigger(TriggerInterface):
    """Asks ``callback`` for the run after the one it is given.

    The callback must answer strictly after the date it receives, or
    ``None`` to stop. Give it a ``description``: the default is built from
    the callback's identity in this process, so it changes on every start —
    and with it the recurring message's identity.
    """

    __slots__ = ("_callback", "_description")

    def __init__(
        self,
        callback: Callable[[datetime], datetime | None],
        description: str | None = None,
    ) -> None:
        """Ask ``callback`` for each next run; describe the trigger as ``description``."""
        self._callback = callback
        self._description = description if description is not None else str(id(callback))

    @override
    def __str__(self) -> str:
        return self._description

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        return self._callback(run)
