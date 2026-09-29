"""Spreads another trigger's runs by a random delay."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_scheduler._time import microseconds
from xtr_scheduler.exception import InvalidArgumentError

from .abstract_decorated_trigger import AbstractDecoratedTrigger

if TYPE_CHECKING:
    from datetime import datetime

    from .trigger_interface import TriggerInterface

__all__ = ["JitterTrigger"]


@final
class JitterTrigger(AbstractDecoratedTrigger):
    """Delays each of another trigger's runs by up to ``max_seconds``, at random.

    So a fleet of processes, or many tasks due at the same minute, do not all
    start at once. The delay is not carried forward: the next run is computed
    from the undelayed one, so the runs do not drift. A delay longer than the
    interval makes runs land out of their order; they come in the order they
    land, none of them lost.

    Each run's delay is drawn from the run itself, the wrapped trigger and
    ``key``, so every process — and every restart — delays one run the same
    way: a run already sent is recognised as such instead of coming back
    under a new delay. Different keys spread tasks sharing a trigger.
    """

    __slots__: tuple[str, ...] = ("_key", "_max_seconds", "_random")

    def __init__(
        self,
        trigger: TriggerInterface,
        max_seconds: int = 60,
        *,
        random_source: random.Random | None = None,
        key: str = "",
    ) -> None:
        """Delay ``trigger``'s runs by 0 to ``max_seconds`` seconds.

        ``random_source``, when given, draws every delay instead — delays
        that no other process, nor a restart, repeats.

        Raises:
            InvalidArgumentError: If ``max_seconds`` is not positive.
        """
        if max_seconds <= 0:
            raise InvalidArgumentError('The "max_seconds" argument must be greater than zero.')
        super().__init__(trigger)
        self._max_seconds = max_seconds
        self._random = random_source
        self._key = key

    @override
    def __str__(self) -> str:
        return f"{self._inner} with 0-{self._max_seconds} second jitter"

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        # ``run`` is a delayed instant, and delayed runs may land out of order when the
        # delay outlasts the interval: the next one is the earliest landing after ``run``
        # of any undelayed run a delay could carry past it.
        earliest: datetime | None = None
        candidate = self._inner.get_next_run_date(run - timedelta(seconds=self._max_seconds))
        # A run after the earliest landing lands after it too.
        while candidate is not None and (earliest is None or candidate < earliest):
            delayed = candidate + timedelta(seconds=self._delay_of(candidate))
            if delayed > run and (earliest is None or delayed < earliest):
                earliest = delayed
            advanced = self._inner.get_next_run_date(candidate)
            if advanced is not None and advanced <= candidate:
                # A trigger that does not move forward: answer its run as it is, and
                # let the scheduler report it rather than end the schedule quietly.
                return earliest if earliest is not None else delayed
            candidate = advanced
        return earliest

    def _delay_of(self, run: datetime) -> int:
        """Return the delay of the undelayed ``run``, in whole seconds."""
        if self._random is not None:
            return self._random.randint(0, self._max_seconds)
        seed = f"{self._key}|{self._inner}|{microseconds(run)}"
        return random.Random(seed).randint(0, self._max_seconds)  # noqa: S311 — spreading load, not secrecy
