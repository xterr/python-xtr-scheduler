"""A message sent over and over, on a trigger."""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from xtr_messenger import RedispatchMessage

from tests.support.contexts import a_context
from tests.support.messages import Named, Plain
from xtr_scheduler import RecurringMessage
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger import (
    CallbackMessageProvider,
    CronExpressionTrigger,
    JitterTrigger,
    PeriodicalTrigger,
    StaticMessageProvider,
)

pytestmark = pytest.mark.anyio


def test_a_hashed_expression_picks_from_the_message_s_string_form() -> None:
    task = Named("my task")

    assert str(RecurringMessage.cron("#midnight", task).get_trigger()) == str(
        CronExpressionTrigger.from_spec("#midnight", "my task")
    )


def test_a_hashed_expression_needs_a_message_with_a_string_form() -> None:
    with pytest.raises(InvalidArgumentError, match="must be stringable"):
        _ = RecurringMessage.cron("#midnight", Plain())


def test_the_id_is_stable_and_differs_between_recurring_messages() -> None:
    first = RecurringMessage.cron("* * * * *", Plain())
    again = RecurringMessage.cron("* * * * *", Plain())
    other = RecurringMessage.cron("* 5 * * *", Plain())
    other_message = RecurringMessage.cron("* * * * *", Plain(1))

    assert first.id == again.id
    assert len({first.id, other.id, other_message.id}) == 3


def test_the_id_is_the_same_in_another_process() -> None:
    script = (
        "from tests.support.messages import Named;"
        "from xtr_scheduler import RecurringMessage;"
        "print(RecurringMessage.every('1 hour', Named('report')).id)"
    )
    here = RecurringMessage.every("1 hour", Named("report")).id

    there = subprocess.run(  # noqa: S603 — a fresh interpreter, running a fixed script
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parents[2],
    ).stdout.strip()

    assert there == here


def test_every_builds_a_periodical_trigger() -> None:
    recurring = RecurringMessage.every(timedelta(minutes=5), Plain())

    assert isinstance(recurring.get_trigger(), PeriodicalTrigger)
    assert str(recurring.get_trigger()) == "every 300 seconds"


def test_a_plain_message_is_described_by_its_type_and_its_string_form() -> None:
    assert str(RecurringMessage.every(60, Plain()).get_provider()) == "Plain"
    assert str(RecurringMessage.every(60, Named("report")).get_provider()) == "Named (report)"


def test_a_message_provider_is_used_as_it_is() -> None:
    provider = StaticMessageProvider(["a"], "mine")

    assert RecurringMessage.every(60, provider).get_provider() is provider


async def test_it_produces_what_its_provider_produces() -> None:
    recurring = RecurringMessage.every(
        60, CallbackMessageProvider(lambda context: [context.name, "x"], "per-run")
    )

    assert [m async for m in recurring.get_messages(a_context("tenants"))] == ["tenants", "x"]


def test_with_jitter_returns_a_new_recurring_message_on_a_jitter_trigger() -> None:
    recurring = RecurringMessage.every(60, Plain())

    jittered = recurring.with_jitter(15)

    assert isinstance(jittered.get_trigger(), JitterTrigger)
    assert jittered.get_provider() is recurring.get_provider()
    assert jittered.id != recurring.id
    assert isinstance(recurring.get_trigger(), PeriodicalTrigger)


def test_a_message_no_codec_can_carry_is_identified_by_its_repr() -> None:
    first = RecurringMessage.every(60, RedispatchMessage(Named("a"), "urgent"))
    again = RecurringMessage.every(60, RedispatchMessage(Named("a"), "urgent"))
    other = RecurringMessage.every(60, RedispatchMessage(Named("b"), "urgent"))

    assert first.id == again.id
    assert first.id != other.id


def test_two_windows_of_one_message_are_two_recurring_messages() -> None:
    message = Plain()
    first = RecurringMessage.every("1 hour", message, until="2026-06-01T00:00:00+00:00")
    second = RecurringMessage.every("1 hour", message, until="2027-06-01T00:00:00+00:00")

    assert first.id != second.id
