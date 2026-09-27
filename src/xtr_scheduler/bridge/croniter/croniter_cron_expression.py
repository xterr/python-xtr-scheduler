"""A cron expression read by croniter."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, final

from croniter import croniter
from typing_extensions import override

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger.cron_expression_interface import CronExpressionInterface

if TYPE_CHECKING:
    from datetime import tzinfo

__all__ = ["CroniterCronExpression"]


@final
class CroniterCronExpression(CronExpressionInterface):
    """Five-field cron, plus ``@daily``-style aliases and ``5#3`` for the third Friday.

    Validated when built, so a typo fails where the schedule is declared
    rather than on the first run. Matches are computed on the wall clock of
    the timezone given: a time that does not exist when clocks go forward
    runs at the first time that does, and an hour that repeats when clocks
    go back matches each time it comes round.
    """

    __slots__ = ("_expression",)

    def __init__(self, expression: str) -> None:
        """Read ``expression``.

        Raises:
            InvalidArgumentError: If ``expression`` is not valid cron.
        """
        if not croniter.is_valid(expression):
            raise InvalidArgumentError(f'Invalid cron expression "{expression}".')
        self._expression = expression

    @override
    def next_after(self, run: datetime, timezone: tzinfo, /) -> datetime:
        # A plain datetime: croniter's arithmetic breaks on a subclass overriding
        # replace(), such as the clock's DatePoint.
        start = datetime.fromtimestamp(run.timestamp(), tz=timezone)
        found: datetime = croniter(self._expression, start).get_next(datetime)
        return found

    @override
    def __str__(self) -> str:
        return self._expression
