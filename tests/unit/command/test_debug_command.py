"""``debug:scheduler``: what each schedule runs, and when it runs next."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_cache.adapter import ArrayAdapter
from xtr_clock.testing import mock_time
from xtr_console import Application, CommandTester, ExitCode
from xtr_console.command import CommandInvokerInterface
from xtr_console.exception import MissingContainerError

from tests.support.dates import at
from tests.support.messages import Named
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.command import DebugCommand
from xtr_scheduler.command.debug_command import _format_interval
from xtr_scheduler.generator import Checkpoint
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_console.command import CommandArguments, CommandDescriptor, CommandSignature

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


@final
class _BuildWithSchedules(CommandInvokerInterface):
    """Builds ``DebugCommand`` with the schedules a container would have supplied."""

    def __init__(self, schedules: ScheduleProviderLocator) -> None:
        self._schedules = schedules

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        del command, signature
        call = cast("Callable[..., object]", DebugCommand(self._schedules))
        result = call(*arguments.args, **arguments.kwargs)
        return await result if inspect.isawaitable(result) else result


def schedules(**named: Schedule) -> ScheduleProviderLocator:
    return ScheduleProviderLocator(named)


def _tester(listed: ScheduleProviderLocator) -> CommandTester:
    """Build a tester whose invoker hands ``DebugCommand`` the schedules ``listed``."""
    application = Application(catch_exceptions=False)
    application.use_invoker(_BuildWithSchedules(listed))
    return CommandTester(application, "debug:scheduler")


async def run(listed: ScheduleProviderLocator, *args: str) -> tuple[int, str]:
    """Run the command with the clock frozen at the start of 2026; return code and display."""
    command = _tester(listed)
    with mock_time(START):
        code = await command.execute(list(args))
    return code, command.display


def every(seconds: int, name: str, until: str = "3000-01-01T00:00:00+00:00") -> RecurringMessage:
    return RecurringMessage.every(seconds, Named(name), from_=START, until=until)


async def test_it_lists_each_schedule_with_the_next_run_of_each_message() -> None:
    code, display = await run(
        schedules(default=Schedule(every(60, "ping")), reports=Schedule(every(3600, "report")))
    )

    assert code == ExitCode.SUCCESS
    assert "default" in display
    assert "reports" in display
    assert "every 60 seconds" in display
    assert "Named (ping)" in display
    assert "2026-01-01T00:01:00+00:00" in display
    assert "1 min" in display
    assert "1 h" in display


async def test_only_the_schedules_named_are_listed() -> None:
    _code, display = await run(
        schedules(default=Schedule(every(60, "ping")), reports=Schedule(every(3600, "report"))),
        "reports",
    )

    assert "report" in display
    assert "ping" not in display


async def test_next_runs_are_computed_from_the_date_given() -> None:
    _code, display = await run(
        schedules(default=Schedule(every(60, "ping"))), "--date", "2026-01-01T05:00:30+00:00"
    )

    assert "computed from 2026-01-01T05:00:30+00:00" in display
    assert "2026-01-01T05:01:00+00:00" in display


async def test_ended_messages_are_hidden_unless_all_are_asked_for() -> None:
    ended = every(60, "gone", until="2026-01-01T00:00:30+00:00")
    listed = schedules(default=Schedule(ended, every(60, "live")))

    _code, hidden = await run(listed)
    _code, shown = await run(listed, "--all")

    assert "gone" not in hidden
    assert "gone" in shown


async def test_sorting_orders_by_next_run() -> None:
    _code, display = await run(
        schedules(default=Schedule(every(3600, "slow"), every(60, "fast"))), "--sort"
    )

    assert display.index("fast") < display.index("slow")


async def test_a_stateful_schedule_is_listed_from_where_it_got_to() -> None:
    cache = ArrayAdapter()
    await Checkpoint("scheduler_checkpoint_default", cache=cache).save(
        at("2026-01-01T10:00:00+00:00"), 0
    )

    _code, display = await run(schedules(default=Schedule(every(60, "ping")).stateful(cache)))

    assert "is stateful" in display
    assert "2026-01-01T10:01:00+00:00" in display


async def test_an_empty_schedule_is_reported() -> None:
    _code, display = await run(schedules(default=Schedule()))

    assert "No recurring messages found" in display


async def test_no_schedule_at_all_is_an_error() -> None:
    code, _display = await run(schedules())

    assert code == ExitCode.INVALID


async def test_an_unknown_schedule_is_an_error() -> None:
    code, _display = await run(schedules(default=Schedule()), "nope")

    assert code == ExitCode.FAILURE


async def test_a_date_it_cannot_read_is_an_error() -> None:
    code, _display = await run(schedules(default=Schedule(every(60, "ping"))), "--date", "pigs fly")

    assert code == ExitCode.INVALID


async def test_without_a_container_the_console_reports_the_missing_schedules() -> None:
    command = CommandTester(Application(catch_exceptions=False), "debug:scheduler")

    with pytest.raises(MissingContainerError, match="schedules"):
        _ = await command.execute()


def test_the_command_requires_its_schedules() -> None:
    construct = cast("Callable[..., object]", DebugCommand)
    with pytest.raises(TypeError):
        _ = construct()


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        ("2026-01-01T00:00:00+00:00", "0 s"),
        ("2026-01-01T00:00:00.250000+00:00", "0.25 s"),
        ("2026-01-01T01:02:03+00:00", "1 h, 2 min, 3 s"),
        ("2027-03-05T00:00:00+00:00", "1 y, 2 mo, 4 d"),
        ("2025-12-31T23:59:00+00:00", "-1 min"),
    ],
)
def test_intervals_read_in_calendar_units(end: str, expected: str) -> None:
    assert _format_interval(at(START), at(end)) == expected
