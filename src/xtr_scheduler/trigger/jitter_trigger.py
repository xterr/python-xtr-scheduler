"""Spreads another trigger's runs by a random delay."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING, final

from typing_extensions import override

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
    from the undelayed one, so the runs do not drift.
    """

    def __init__(
        self,
        trigger: TriggerInterface,
        max_seconds: int = 60,
        *,
        random_source: random.Random | None = None,
    ) -> None:
        """Delay ``trigger``'s runs by 0 to ``max_seconds`` seconds, drawn from ``random_source``.

        Raises:
            InvalidArgumentError: If ``max_seconds`` is not positive.
        """
        if max_seconds <= 0:
            raise InvalidArgumentError('The "max_seconds" argument must be greater than zero.')
        super().__init__(trigger)
        self._max_seconds = max_seconds
        self._random = random_source if random_source is not None else random.Random()  # noqa: S311 — spreading load, not secrecy

    @override
    def __str__(self) -> str:
        return f"{self._inner} with 0-{self._max_seconds} second jitter"

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        # ``run`` includes a delay; step back past any delay to find the undelayed run.
        next_run = self._inner.get_next_run_date(run - timedelta(seconds=self._max_seconds))
        if next_run is None:
            return None
        # That may be the run that just happened: move on to the one after it.
        while next_run <= run:
            advanced = self._inner.get_next_run_date(next_run)
            if advanced is None:
                return None
            if advanced <= next_run:
                break
            next_run = advanced
        return next_run + timedelta(seconds=self._random.randint(0, self._max_seconds))
