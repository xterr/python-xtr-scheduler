"""Turning a schedule into messages as they fall due, each exactly once."""

from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_cache.adapter import ArrayAdapter
from xtr_clock import MockClock
from xtr_lock import InMemoryStore, Key, Lock

from tests.support.flaky_cache import FlakyCache
from tests.support.messages import Named, Plain
from tests.support.scripted_trigger import ScriptedTrigger, moment
from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.exception import SchedulerLogicError, SchedulerRuntimeError
from xtr_scheduler.generator import Checkpoint, MessageGenerator
from xtr_scheduler.trigger import TriggerInterface

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

pytestmark = pytest.mark.anyio

FIRST, SECOND, THIRD = Named("first"), Named("second"), Named("third")


def scripted(message: object, *runs: str) -> RecurringMessage:
    return RecurringMessage.trigger(ScriptedTrigger(*runs), message)


async def drain(generator: MessageGenerator) -> list[object]:
    return [message async for _context, message in generator.get_messages()]


async def collect_into(sent: list[object], generator: MessageGenerator) -> None:
    async for _context, message in generator.get_messages():
        sent.append(message)


def clock_at(time: str) -> MockClock:
    return MockClock(moment(time))


def move(clock: MockClock, time: str) -> None:
    clock.modify(moment(time).isoformat())


@final
class NeverAgain(TriggerInterface):
    """A trigger with no run at all."""

    @override
    def __str__(self) -> str:
        return "foo"

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        del run


@final
class Frozen(TriggerInterface):
    """A trigger answering the same date whatever it is asked."""

    @override
    def __str__(self) -> str:
        return "frozen"

    @override
    def get_next_run_date(self, run: datetime, /) -> datetime | None:
        del run
        return moment("22:13:00")


def _first() -> RecurringMessage:
    return scripted(FIRST, "22:13:00", "22:14:00", "22:15:00")


SCENARIOS = [
    pytest.param(
        "22:12:00",
        {"22:12:00": [], "22:12:01": [], "22:13:00": [FIRST], "22:13:01": []},
        [lambda: scripted(FIRST, "22:13:00", "22:14:00")],
        id="first",
    ),
    pytest.param(
        "22:12:00",
        {"22:12:59.999999": [], "22:13:00": [FIRST], "22:13:01": []},
        [_first],
        id="microseconds",
    ),
    pytest.param("22:12:00", {"22:14:01": [FIRST, FIRST]}, [_first], id="skipped"),
    pytest.param(
        "22:12:00",
        {
            "22:12:59": [],
            "22:13:00": [FIRST],
            "22:13:01": [],
            "22:13:59": [],
            "22:14:00": [FIRST],
            "22:14:01": [],
        },
        [_first],
        id="sequence",
    ),
    pytest.param(
        "22:12:00",
        {
            "22:12:00.555": [],
            "22:13:01.555": [THIRD, FIRST, FIRST, SECOND, FIRST],
            "22:13:02": [FIRST],
            "22:13:02.555": [],
        },
        [
            lambda: scripted(FIRST, "22:12:59", "22:13:00", "22:13:01", "22:13:02", "22:13:03"),
            lambda: scripted(SECOND, "22:13:00", "22:14:00"),
            lambda: scripted(THIRD, "22:12:30", "22:13:30"),
        ],
        id="concurrency",
    ),
    pytest.param(
        "22:12:00",
        {"22:12:59": [], "22:13:59": [FIRST, SECOND], "22:14:00": [FIRST, SECOND], "22:14:01": []},
        [_first, lambda: scripted(SECOND, "22:13:00", "22:14:00", "22:15:00")],
        id="parallel",
    ),
    pytest.param(
        "22:12:00",
        {"22:12:01": []},
        [lambda: RecurringMessage.trigger(NeverAgain(), Plain())],
        id="past",
    ),
]


@pytest.mark.parametrize(("start", "runs", "builds"), SCENARIOS)
async def test_messages_come_out_as_they_fall_due(
    start: str, runs: dict[str, list[Named]], builds: list[Callable[[], RecurringMessage]]
) -> None:
    clock = clock_at(start)
    schedule = Schedule(*(build() for build in builds)).stateful(ArrayAdapter())
    generator = MessageGenerator(schedule, "dummy", clock)

    assert await drain(generator) == []
    for time, expected in runs.items():
        move(clock, time)
        assert await drain(generator) == expected


@final
class BuildsOnDemand(ScheduleProviderInterface):
    """Builds its schedule the first time it is asked."""

    def __init__(self, builds: list[Callable[[], RecurringMessage]]) -> None:
        self._builds = builds
        self._schedule: Schedule | None = None

    @override
    def get_schedule(self) -> Schedule:
        if self._schedule is None:
            self._schedule = Schedule(*(build() for build in self._builds))
            _ = self._schedule.stateful(ArrayAdapter())
        return self._schedule


@pytest.mark.parametrize(("start", "runs", "builds"), SCENARIOS)
async def test_a_provider_s_schedule_runs_the_same_way(
    start: str, runs: dict[str, list[Named]], builds: list[Callable[[], RecurringMessage]]
) -> None:
    clock = clock_at(start)
    generator = MessageGenerator(BuildsOnDemand(builds), "dummy", clock)

    assert await drain(generator) == []
    for time, expected in runs.items():
        move(clock, time)
        assert await drain(generator) == expected


async def test_a_message_added_while_running_is_picked_up() -> None:
    clock = clock_at("22:12:00")
    schedule = Schedule(scripted(FIRST, "22:13:00", "22:14:00")).stateful(ArrayAdapter())
    generator = MessageGenerator(schedule, "dummy", clock)
    assert await drain(generator) == []
    runs: dict[str, list[Named]] = {
        "22:12:00": [],
        "22:12:01": [],
        "22:13:00": [FIRST],
        "22:13:01": [],
    }
    for time, expected in runs.items():
        move(clock, time)
        assert await drain(generator) == expected

    added = Named("added-after-start")
    _ = schedule.add(scripted(added, "22:13:10", "22:13:11"))

    assert await drain(generator) == []
    clock.sleep(9)
    assert await drain(generator) == [added]


async def test_each_message_comes_with_the_run_it_belongs_to() -> None:
    clock = clock_at("22:12:00")
    recurring = scripted(Named("message"), "22:13:00", "22:14:00", "22:16:00")
    generator = MessageGenerator(Schedule(recurring).stateful(ArrayAdapter()), "dummy", clock)
    assert await drain(generator) == []
    clock.sleep(2 * 60 + 10)

    contexts = [context async for context, _message in generator.get_messages()]

    assert [(c.triggered_at, c.next_trigger_at) for c in contexts] == [
        (moment("22:13:00"), moment("22:14:00")),
        (moment("22:14:00"), moment("22:16:00")),
    ]
    assert all(c.trigger is recurring.get_trigger() for c in contexts)
    assert all((c.name, c.id) == ("dummy", recurring.id) for c in contexts)


async def test_a_message_is_recorded_when_iteration_stops_early() -> None:
    clock = clock_at("22:12:00")
    cache = ArrayAdapter()
    schedule = Schedule(scripted(Named("message"), "22:13:00", "22:14:00", "22:16:00"))
    checkpoint = Checkpoint("dummy", cache=cache)
    generator = MessageGenerator(schedule.stateful(cache), "dummy", clock, checkpoint)
    assert await drain(generator) == []
    clock.sleep(60 + 10)

    async with aclosing(generator.get_messages()) as messages:
        async for _pair in messages:
            break

    assert checkpoint.time() == moment("22:13:00")


async def test_every_missed_run_is_sent_after_downtime() -> None:
    clock = clock_at("22:15:00")
    cache = ArrayAdapter()
    checkpoint = Checkpoint("dummy", cache=cache)
    schedule = Schedule(RecurringMessage.every("1 minute", Named("message"))).stateful(cache)
    generator = MessageGenerator(schedule, "dummy", clock, checkpoint)

    assert await drain(generator) == []
    assert checkpoint.time() == moment("22:15:00")
    clock.sleep(60 + 10)
    assert len(await drain(generator)) == 1
    clock.sleep(2 * 60)
    assert len(await drain(generator)) == 2
    clock.sleep(5 * 60)
    assert len(await drain(generator)) == 5
    assert checkpoint.time() == moment("22:23:00")


async def test_only_the_latest_missed_run_is_sent_when_the_schedule_asks() -> None:
    clock = clock_at("22:15:00")
    cache = ArrayAdapter()
    recurring = RecurringMessage.every("1 minute", Named("message"), until=moment("22:23:00"))
    schedule = Schedule(recurring).stateful(cache).process_only_last_missed_run()
    generator = MessageGenerator(schedule, "dummy", clock, Checkpoint("dummy", cache=cache))

    assert await drain(generator) == []
    clock.sleep(60 + 10)
    assert len(await drain(generator)) == 1
    clock.sleep(2 * 60)
    assert len(await drain(generator)) == 1
    clock.sleep(5 * 60)
    assert len(await drain(generator)) == 1


async def test_a_batch_left_half_sent_is_finished_by_the_next_process() -> None:
    clock = clock_at("22:12:00")
    cache = ArrayAdapter()

    def process() -> MessageGenerator:
        schedule = Schedule(
            RecurringMessage.every("30 seconds", FIRST),
            RecurringMessage.every("30 seconds", SECOND),
        ).stateful(cache)
        return MessageGenerator(schedule, "dummy", clock, Checkpoint("dummy", cache=cache))

    first_process = process()
    assert await drain(first_process) == []
    clock.sleep(30)
    sent: list[object] = []
    async with aclosing(first_process.get_messages()) as messages:
        async for _context, message in messages:
            sent.append(message)
            break
    assert sent == [FIRST]

    assert await drain(process()) == [SECOND]


@pytest.mark.parametrize("failure", ["readonly", "dead"])
async def test_nothing_is_sent_while_the_state_cannot_be_saved(failure: str) -> None:
    clock = clock_at("22:12:00")
    cache = FlakyCache()
    message = Named("message")

    def process() -> MessageGenerator:
        schedule = Schedule(RecurringMessage.every("1 minute", message)).stateful(cache)
        return MessageGenerator(schedule, "dummy", clock)

    generator = process()
    assert await drain(generator) == []
    clock.sleep(60.5)
    assert await drain(generator) == [message]

    cache.failure = failure
    for _ in range(3):
        clock.sleep(60)
        sent: list[object] = []
        with pytest.raises(SchedulerRuntimeError, match="Failed to save"):
            await collect_into(sent, generator)
        assert sent == []
        generator = process()

    cache.failure = None
    assert await drain(generator) == [message, message, message]
    clock.sleep(60)
    assert await drain(generator) == [message]


async def test_a_run_whose_record_failed_is_sent_again_by_the_next_process() -> None:
    clock = clock_at("22:12:00")
    cache = FlakyCache()
    message = Named("message")
    sent: list[object] = []

    def process() -> MessageGenerator:
        schedule = Schedule(RecurringMessage.every("1 minute", message)).stateful(cache)
        return MessageGenerator(schedule, "dummy", clock)

    async def consume_until_it_fails(generator: MessageGenerator) -> None:
        with pytest.raises(SchedulerRuntimeError):
            await collect_into(sent, generator)

    generator = process()
    assert await drain(generator) == []
    clock.sleep(60.5)

    cache.save_results = [True, False]
    await consume_until_it_fails(generator)
    assert sent == [message]

    cache.save_results = [True, False]
    await consume_until_it_fails(process())
    assert sent == [message, message]

    for _ in range(3):
        cache.save_results = [False]
        await consume_until_it_fails(process())
        assert sent == [message, message]
        clock.sleep(60)


async def test_a_trigger_that_does_not_move_forward_is_refused() -> None:
    clock = clock_at("22:12:00")
    schedule = Schedule(RecurringMessage.trigger(Frozen(), Plain())).stateful(ArrayAdapter())
    generator = MessageGenerator(schedule, "dummy", clock)
    assert await drain(generator) == []
    clock.sleep(2 * 60)

    with pytest.raises(SchedulerLogicError, match='The "frozen" trigger does not move'):
        _ = await drain(generator)


async def test_between_runs_it_says_when_the_next_one_is_due() -> None:
    clock = clock_at("22:12:00")
    generator = MessageGenerator(Schedule(scripted(FIRST, "22:13:00", "22:14:00")), "dummy", clock)

    assert await drain(generator) == []

    assert generator.wait_until == moment("22:13:00")


async def test_a_schedule_with_nothing_left_to_run_stops_for_good() -> None:
    clock = clock_at("22:12:00")
    generator = MessageGenerator(
        Schedule(RecurringMessage.trigger(NeverAgain(), Plain())), "dummy", clock
    )

    assert await drain(generator) == []
    clock.sleep(3600)

    assert await drain(generator) == []
    assert generator.wait_until is None


async def test_closing_hands_the_schedule_s_lock_back() -> None:
    lock = Lock(Key("schedule"), InMemoryStore())
    clock = clock_at("22:12:00")
    generator = MessageGenerator(Schedule(_first()).lock(lock), "dummy", clock)
    assert await drain(generator) == []
    assert await lock.is_acquired()

    await generator.close()

    assert not await lock.is_acquired()


async def test_closing_before_ever_running_does_nothing() -> None:
    await MessageGenerator(Schedule(), "dummy", clock_at("22:12:00")).close()
