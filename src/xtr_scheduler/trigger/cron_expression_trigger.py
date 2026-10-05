"""Runs when a cron expression matches."""

from __future__ import annotations

import hashlib
import random
import re
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import InvalidTimezoneError, resolve_timezone

from xtr_scheduler.exception import InvalidArgumentError, SchedulerLogicError

from .trigger_interface import TriggerInterface

if TYPE_CHECKING:
    from datetime import datetime, tzinfo

    from .cron_expression_interface import CronExpressionInterface

__all__ = ["CronExpressionTrigger"]

#: Shorthands for common hashed expressions.
_HASH_ALIASES: Final = {
    "#hourly": "# * * * *",
    "#daily": "# # * * *",
    "#weekly": "# # * * #",
    "#weekly@midnight": "# #(0-2) * * #",
    "#monthly": "# # # * *",
    "#monthly@midnight": "# #(0-2) # * *",
    "#annually": "# # # # *",
    "#annually@midnight": "# #(0-2) # # *",
    "#yearly": "# # # # *",
    "#yearly@midnight": "# #(0-2) # # *",
    "#midnight": "# #(0-2) * * *",
}

#: The range a bare ``#`` picks from, per field. Days stop at 28 so every
#: month has the day picked.
_HASH_RANGES: Final = ((0, 59), (0, 23), (1, 28), (1, 12), (0, 6))

_HASHED_FIELD: Final = re.compile(r"^#(?:\((\d+)-(\d+)\))?$")
_FIELDS: Final = 5


@final
class CronExpressionTrigger(TriggerInterface):
    """Runs whenever a cron expression matches, on the clock of a timezone.

    A **hashed** expression puts ``#`` where a value would go —
    ``"# # * * *"`` is once a day at a minute and hour picked for the
    message. The pick is derived from a context, the message's string form,
    so every process computes the same one, while different messages land
    at different times rather than all at once. ``#(0-5)`` picks within a
    range, and ``#daily``, ``#midnight`` and the other shorthands expand to
    the common shapes.
    """

    __slots__ = ("_expression", "_timezone")

    def __init__(
        self,
        expression: CronExpressionInterface,
        timezone: tzinfo | str | None = None,
    ) -> None:
        """Run when ``expression`` matches, read in ``timezone`` — ``run``'s own when ``None``.

        Raises:
            InvalidArgumentError: If ``timezone`` names no known timezone.
        """
        self._expression = expression
        self._timezone = _zone(timezone)

    @classmethod
    def from_expression(
        cls,
        expression: str = "* * * * *",
        context: str | None = None,
        timezone: tzinfo | str | None = None,
    ) -> CronExpressionTrigger:
        """Build a trigger from the text of an expression, hashed or not.

        Raises:
            SchedulerLogicError: If the expression is hashed and no
                ``context`` is given, or no cron library is installed.
            InvalidArgumentError: If the expression is not valid cron.
        """
        if cls.is_hashed(expression):
            if context is None:
                raise SchedulerLogicError(
                    'A context must be provided to use "hashed" cron expressions.'
                )
            expression = _unhash(expression, context)
        try:
            # The cron bridge is behind an extra.
            from xtr_scheduler.bridge.croniter import (  # noqa: PLC0415 — optional extra
                CroniterCronExpression,
            )
        except ImportError as exc:  # pragma: no cover — the cron extra is a dev dependency
            raise SchedulerLogicError(
                'Cron expressions need a cron library: install "xtr-scheduler[cron]".'
            ) from exc
        return cls(CroniterCronExpression(expression), timezone)

    @staticmethod
    def is_hashed(expression: str) -> bool:
        """Tell whether ``expression`` has a hashed field — ``5#3``, the third Friday, has not."""
        if expression in _HASH_ALIASES:
            return True
        return any(_HASHED_FIELD.match(part) for part in expression.split())

    @override
    def __str__(self) -> str:
        return str(self._expression)

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        zone = self._timezone if self._timezone is not None else run.tzinfo
        if zone is None:
            raise InvalidArgumentError(f"The run date {run.isoformat()} has no timezone.")
        return self._expression.next_after(run, zone)


def _zone(timezone: tzinfo | str | None) -> tzinfo | None:
    """Read ``timezone`` as the clock reads one — a name, ``"Z"``, an offset such as ``"+02:00"``.

    Raises:
        InvalidArgumentError: If it names no zone.
    """
    if not isinstance(timezone, str):
        return timezone
    try:
        return resolve_timezone(timezone)
    except InvalidTimezoneError as exc:
        raise InvalidArgumentError(f'The timezone "{timezone}" is not known.') from exc


def _unhash(expression: str, context: str) -> str:
    """Replace each hashed field by the value ``context`` picks for it."""
    expression = _HASH_ALIASES.get(expression, expression)
    parts = expression.split(" ")
    if len(parts) != _FIELDS:
        return expression
    seed = int.from_bytes(hashlib.sha256(context.encode()).digest(), "big")
    picker = random.Random(seed)  # noqa: S311 — spreading load, not secrecy
    for position, part in enumerate(parts):
        matched = _HASHED_FIELD.match(part)
        if matched is None:
            continue
        low, high = _HASH_RANGES[position]
        if matched.group(1) is not None:
            low, high = int(matched.group(1)), int(matched.group(2))
        parts[position] = str(picker.randint(low, high))
    return " ".join(parts)
