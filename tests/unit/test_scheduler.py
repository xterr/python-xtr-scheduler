"""Runs schedules in-process, without a message bus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

import pytest
from typing_extensions import override
from xtr_clock import ClockInterface, MockClock
from xtr_event_dispatcher import EventDispatcher
from xtr_lock import InMemoryStore, Key, Lock

from tests.support.messages import Named, Plain
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.event import FailureEvent, PostRunEvent, PreRunEvent
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.scheduler import Scheduler

if TYPE_CHECKING:
    from datetime import tzinfo

    from xtr_clock import DatePoint

pytestmark = pytest.mark.anyio

START = "2026-01-01T00:00:00+00:00"


def every_minute(message: object) -> Schedule:
    return Schedule(RecurringMessage.every(60, message, from_=START))


@final
class Handler:
    """Records messages, stops the scheduler after ``count``, and may fail on one."""

    def __init__(self, count: int, fail_on: object = None) -> None:
        self.scheduler: Scheduler | None = None
        self.seen: list[object] = []
        self._count = count
        self._fail_on = fail_on

    async def __call__(self, message: object) -> str:
        self.seen.append(message)
        if len(self.seen) >= self._count and self.scheduler is not None:
            self.scheduler.stop()
        if message == self._fail_on:
            raise ValueError("boom")
        return f"handled {message}"


def scheduler_for(
    handler: Handler, *schedules: Schedule, events: EventDispatcher | None = None
) -> tuple[Scheduler, MockClock]:
    clock = MockClock(START)
    scheduler = Scheduler({Named: handler}, schedules, clock, events)
    handler.scheduler = scheduler
    return scheduler, clock


async def test_it_hands_each_due_message_to_the_handler_for_its_type() -> None:
    handler = Handler(3)
    scheduler, clock = scheduler_for(handler, every_minute(Named("tick")))

    await scheduler.run()

    assert handler.seen == [Named("tick")] * 3
    assert clock.now().isoformat() == "2026-01-01T00:03:00+00:00"


async def test_it_runs_every_schedule_given() -> None:
    handler = Handler(2)
    scheduler, _clock = scheduler_for(handler, every_minute(Named("a")), every_minute(Named("b")))

    await scheduler.run()

    assert handler.seen == [Named("a"), Named("b")]


async def test_runs_are_announced_and_their_results_reported() -> None:
    events = EventDispatcher()
    seen: list[tuple[str, object]] = []

    def before(event: PreRunEvent) -> None:
        seen.append(("pre", event.message))

    def after(event: PostRunEvent) -> None:
        seen.append(("post", event.result))

    events.add_listener(PreRunEvent, before)
    events.add_listener(PostRunEvent, after)
    scheduler, _clock = scheduler_for(Handler(1), every_minute(Named("a")), events=events)

    await scheduler.run()

    assert seen == [("pre", Named("a")), ("post", "handled a")]


async def test_a_cancelled_run_is_not_handled() -> None:
    events = EventDispatcher()
    cancelled: list[object] = []

    def cancel_first(event: PreRunEvent) -> None:
        if not cancelled:
            cancelled.append(event.message)
            _ = event.should_cancel(value=True)

    events.add_listener(PreRunEvent, cancel_first)
    handler = Handler(1)
    scheduler, clock = scheduler_for(handler, every_minute(Named("a")), events=events)

    await scheduler.run()

    assert cancelled == [Named("a")]
    assert handler.seen == [Named("a")]
    assert clock.now().isoformat() == "2026-01-01T00:02:00+00:00"


async def test_a_failure_is_raised_unless_a_listener_ignores_it() -> None:
    handler = Handler(1, fail_on=Named("a"))
    scheduler, _clock = scheduler_for(handler, every_minute(Named("a")), events=EventDispatcher())

    with pytest.raises(ValueError, match="boom"):
        await scheduler.run()


async def test_an_ignored_failure_lets_the_scheduler_carry_on() -> None:
    events = EventDispatcher()
    failures: list[BaseException] = []

    def ignore(event: FailureEvent) -> None:
        failures.append(event.error)
        _ = event.should_ignore(value=True)

    events.add_listener(FailureEvent, ignore)
    handler = Handler(2, fail_on=Named("a"))
    scheduler, _clock = scheduler_for(handler, every_minute(Named("a")), events=events)

    await scheduler.run()

    assert len(failures) == 2
    assert handler.seen == [Named("a"), Named("a")]


async def test_a_run_hands_the_schedules_lock_back_when_it_returns() -> None:
    lock = Lock(Key("schedule"), InMemoryStore())
    handler = Handler(2)
    scheduler, _clock = scheduler_for(handler, every_minute(Named("tick")).lock(lock))

    await scheduler.run()

    assert not await lock.is_acquired()


async def test_a_message_type_with_no_handler_is_refused_naming_the_registered_ones() -> None:
    clock = MockClock(START)
    scheduler = Scheduler({Named: Handler(1)}, [every_minute(Plain())], clock)

    with pytest.raises(InvalidArgumentError, match=r"No handler is registered for .Plain.*Named"):
        await scheduler.run()


async def test_the_sleep_between_polls_is_never_negative() -> None:
    slow = SlowClock(START)
    scheduler = Scheduler({Named: Handler(1)}, [], slow)
    slow.scheduler = scheduler

    await scheduler.run(sleep=1.0)

    assert slow.slept == [0.0]


@final
class SlowClock(ClockInterface):
    """A clock whose second reading jumps past a poll interval, recording what it sleeps."""

    def __init__(self, start: str) -> None:
        self._mock = MockClock(start)
        self.slept: list[float] = []
        self.scheduler: Scheduler | None = None
        self._reads = 0

    @override
    def now(self) -> DatePoint:
        self._reads += 1
        if self._reads > 1:
            self._mock.sleep(5)
        return self._mock.now()

    @override
    def sleep(self, seconds: float) -> None:
        self._mock.sleep(seconds)

    @override
    async def sleep_async(self, seconds: float) -> None:
        self.slept.append(seconds)
        if self.scheduler is not None:
            self.scheduler.stop()

    @override
    def with_timezone(self, timezone: str | tzinfo) -> Self:
        del timezone
        return self
