"""Turns a worker's events about a scheduled message into scheduler events."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_messenger import Envelope, HandledStamp, RedispatchMessage
from xtr_messenger.event import (
    WorkerMessageFailedEvent,
    WorkerMessageHandledEvent,
    WorkerMessageReceivedEvent,
)

from tests.support.contexts import a_context
from tests.support.messages import Named
from xtr_scheduler import Schedule
from xtr_scheduler.event import FailureEvent, PostRunEvent, PreRunEvent
from xtr_scheduler.event_listener import DispatchSchedulerEventListener
from xtr_scheduler.messenger import ScheduledStamp
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

pytestmark = pytest.mark.anyio

STAMP = ScheduledStamp.from_context(a_context("default"))


def listener(schedule: Schedule, app: EventDispatcher) -> DispatchSchedulerEventListener:
    return DispatchSchedulerEventListener(ScheduleProviderLocator({"default": schedule}), app)


def scheduled(message: object) -> Envelope:
    return Envelope(message, (STAMP,))


async def test_a_received_message_is_announced_before_its_run() -> None:
    app, schedule = EventDispatcher(), Schedule()
    seen: list[PreRunEvent] = []
    app.add_listener(PreRunEvent, seen.append)
    event = WorkerMessageReceivedEvent(scheduled(Named("a")), "scheduler_default")

    await listener(schedule, app).on_message_received(event)

    [pre_run] = seen
    assert (pre_run.schedule, pre_run.message) == (schedule, Named("a"))
    assert pre_run.context.name == "default"
    assert event.should_handle()


async def test_a_cancelled_run_is_skipped_by_the_worker() -> None:
    schedule = Schedule()

    def cancel(event: PreRunEvent) -> None:
        _ = event.should_cancel(value=True)

    _ = schedule.before(cancel)
    event = WorkerMessageReceivedEvent(scheduled(Named("a")), "scheduler_default")

    await listener(schedule, EventDispatcher()).on_message_received(event)

    assert not event.should_handle()


async def test_a_handled_run_is_announced_with_its_result() -> None:
    app = EventDispatcher()
    seen: list[PostRunEvent] = []
    app.add_listener(PostRunEvent, seen.append)
    envelope = scheduled(Named("a")).with_stamps(HandledStamp("handler", 42))

    await listener(Schedule(), app).on_message_handled(WorkerMessageHandledEvent(envelope, "t"))

    assert [event.result for event in seen] == [42]


async def test_a_failed_run_is_announced_with_its_error() -> None:
    app = EventDispatcher()
    seen: list[FailureEvent] = []
    app.add_listener(FailureEvent, seen.append)
    error = ValueError("boom")

    await listener(Schedule(), app).on_message_failed(
        WorkerMessageFailedEvent(scheduled(Named("a")), "t", error)
    )

    assert [event.error for event in seen] == [error]


async def test_listeners_see_the_message_inside_a_redispatch() -> None:
    app = EventDispatcher()
    seen: list[PreRunEvent] = []
    app.add_listener(PreRunEvent, seen.append)
    envelope = scheduled(RedispatchMessage(Envelope(Named("inner"), (STAMP,))))

    await listener(Schedule(), app).on_message_received(WorkerMessageReceivedEvent(envelope, "t"))

    assert [event.message for event in seen] == [Named("inner")]


async def test_the_application_hears_first_and_the_schedule_after() -> None:
    order: list[str] = []
    app, schedule = EventDispatcher(), Schedule()
    app.add_listener(PostRunEvent, lambda: order.append("app"))
    _ = schedule.after(lambda: order.append("schedule"))

    await listener(schedule, app).on_message_handled(
        WorkerMessageHandledEvent(scheduled(Named("a")), "t")
    )

    assert order == ["app", "schedule"]


async def test_messages_not_from_a_known_schedule_are_left_alone() -> None:
    app = EventDispatcher()
    seen: list[object] = []
    app.add_listener(PreRunEvent, seen.append)
    handler = listener(Schedule(), app)
    other = ScheduledStamp.from_context(a_context("elsewhere"))

    await handler.on_message_received(WorkerMessageReceivedEvent(Envelope(Named("a")), "t"))
    await handler.on_message_received(
        WorkerMessageReceivedEvent(Envelope(Named("a"), (other,)), "t")
    )

    assert seen == []


def test_it_subscribes_to_the_three_message_events() -> None:
    assert set(DispatchSchedulerEventListener.get_subscribed_events()) == {
        WorkerMessageReceivedEvent,
        WorkerMessageHandledEvent,
        WorkerMessageFailedEvent,
    }
