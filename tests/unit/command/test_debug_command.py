"""``debug:scheduler``: what each schedule runs, and when it runs next."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_cache.adapter import ArrayAdapter
from xtr_clock.testing import mock_time
from xtr_console import Application, CommandTester, ExitCode

from tests.support.dates import at
from tests.support.messages import Named
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.command import DebugCommand
from xtr_scheduler.command.debug_command import format_interval
from xtr_scheduler.generator import Checkpoint
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


def schedules(**named: Schedule) -> ScheduleProviderLocator:
    return ScheduleProviderLocator(named)


@pytest.fixture
def tester() -> Iterator[CommandTester]:
    yield CommandTester(Application(catch_exceptions=False), "debug:scheduler")
    DebugCommand.use_schedules(None)


async def run(tester: CommandTester, *args: str) -> int:
    """Run the command with the clock frozen at the start of 2026."""
    with mock_time(START):
        return await tester.execute(list(args))


def every(seconds: int, name: str, until: str = "3000-01-01T00:00:00+00:00") -> RecurringMessage:
    return RecurringMessage.every(seconds, Named(name), from_=START, until=until)


async def test_it_lists_each_schedule_with_the_next_run_of_each_message(
    tester: CommandTester,
) -> None:
    DebugCommand.use_schedules(
        schedules(default=Schedule(every(60, "ping")), reports=Schedule(every(3600, "report")))
    )

    code = await run(tester)

    display = tester.display
    assert code == ExitCode.SUCCESS
    assert "default" in display
    assert "reports" in display
    assert "every 60 seconds" in display
    assert "Named (ping)" in display
    assert "2026-01-01T00:01:00+00:00" in display
    assert "1 min" in display
    assert "1 h" in display


async def test_only_the_schedules_named_are_listed(tester: CommandTester) -> None:
    DebugCommand.use_schedules(
        schedules(default=Schedule(every(60, "ping")), reports=Schedule(every(3600, "report")))
    )

    _ = await run(tester, "reports")

    assert "report" in tester.display
    assert "ping" not in tester.display


async def test_next_runs_are_computed_from_the_date_given(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules(default=Schedule(every(60, "ping"))))

    _ = await run(tester, "--date", "2026-01-01T05:00:30+00:00")

    assert "computed from 2026-01-01T05:00:30+00:00" in tester.display
    assert "2026-01-01T05:01:00+00:00" in tester.display


async def test_ended_messages_are_hidden_unless_all_are_asked_for(tester: CommandTester) -> None:
    ended = every(60, "gone", until="2026-01-01T00:00:30+00:00")
    DebugCommand.use_schedules(schedules(default=Schedule(ended, every(60, "live"))))

    _ = await run(tester)
    hidden = tester.display
    _ = await run(tester, "--all")

    assert "gone" not in hidden
    assert "gone" in tester.display


async def test_sorting_orders_by_next_run(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules(default=Schedule(every(3600, "slow"), every(60, "fast"))))

    _ = await run(tester, "--sort")

    display = tester.display
    assert display.index("fast") < display.index("slow")


async def test_a_stateful_schedule_is_listed_from_where_it_got_to(tester: CommandTester) -> None:
    cache = ArrayAdapter()
    await Checkpoint("scheduler_checkpoint_default", cache=cache).save(
        at("2026-01-01T10:00:00+00:00"), 0
    )
    DebugCommand.use_schedules(schedules(default=Schedule(every(60, "ping")).stateful(cache)))

    _ = await run(tester)

    assert "is stateful" in tester.display
    assert "2026-01-01T10:01:00+00:00" in tester.display


async def test_an_empty_schedule_is_reported(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules(default=Schedule()))

    _ = await run(tester)

    assert "No recurring messages found" in tester.display


async def test_no_schedule_at_all_is_an_error(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules())

    assert await run(tester) == ExitCode.INVALID


async def test_an_unknown_schedule_is_an_error(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules(default=Schedule()))

    assert await run(tester, "nope") == ExitCode.FAILURE


async def test_a_date_it_cannot_read_is_an_error(tester: CommandTester) -> None:
    DebugCommand.use_schedules(schedules(default=Schedule(every(60, "ping"))))

    assert await run(tester, "--date", "when pigs fly") == ExitCode.INVALID


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
    assert format_interval(at(START), at(end)) == expected
