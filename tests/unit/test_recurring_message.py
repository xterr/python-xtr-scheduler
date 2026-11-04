"""A message sent over and over, on a trigger."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from xtr_messenger import Envelope, RedispatchMessage, TransportNamesStamp

from tests.support.contexts import a_context
from tests.support.identified_messages import (
    RotateToken,
    quotas,
    refused_pairs,
    restock,
    unwritable_pairs,
)
from tests.support.messages import Named, Plain
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.trigger import (
    CallbackMessageProvider,
    CronExpressionTrigger,
    JitterTrigger,
    PeriodicalTrigger,
    StaticMessageProvider,
)

pytestmark = pytest.mark.anyio

_IDS_SCRIPT = (
    "from tests.support.identified_messages import RotateToken, quotas, refused_pairs, restock;"
    "from xtr_scheduler import RecurringMessage;"
    "refused = [m for pair in refused_pairs().values() for m in pair];"
    "print(*(RecurringMessage.every('1 hour', m).id"
    " for m in (quotas(), restock(), RotateToken('acme', 'token-A'), *refused)))"
)
# The ids of the messages' providers: written from the messages alone, so they hold whatever
# the package is installed as, where the recurring message's own id also names its classes.
_EXACT_PROVIDER_IDS = ["_rgdJDW", "fQRA8i9", "IhxEFOa", "_zjyq8L"]


def _ids_under_hash_seed(seed: str) -> str:
    return subprocess.run(  # noqa: S603 — a fresh interpreter, running a fixed script
        [sys.executable, "-c", _IDS_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parents[2],
        env={**os.environ, "PYTHONHASHSEED": seed},
    ).stdout.strip()


def test_a_hashed_expression_picks_from_the_message_s_string_form() -> None:
    task = Named("my task")

    assert str(RecurringMessage.cron("#midnight", task).get_trigger()) == str(
        CronExpressionTrigger.from_expression("#midnight", "my task")
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


def test_the_id_is_the_same_under_every_hash_seed() -> None:
    ids = {seed: _ids_under_hash_seed(seed) for seed in ("1", "2", "3")}

    assert len(set(ids.values())) == 1, ids
    assert len(ids["1"].split()) == 3 + 2 * len(refused_pairs())


def test_the_ids_of_exactly_written_messages_hold() -> None:
    messages = [quotas(), restock(), RotateToken("acme", "token-A"), RotateToken("acme", "token-B")]

    ids = [RecurringMessage.every("1 hour", m).get_provider().id for m in messages]

    assert ids == _EXACT_PROVIDER_IDS


@pytest.mark.parametrize(("first", "second"), refused_pairs().values(), ids=refused_pairs().keys())
def test_a_message_the_serializer_refuses_is_identified_by_its_data(
    first: object, second: object
) -> None:
    one = RecurringMessage.cron("0 9 * * *", first)
    two = RecurringMessage.cron("0 9 * * *", second)

    schedule = Schedule(one, two)

    assert one.id != two.id
    assert len(schedule.recurring_messages) == 2


@pytest.mark.parametrize(
    ("first", "second"), unwritable_pairs().values(), ids=unwritable_pairs().keys()
)
def test_a_message_nothing_can_write_is_identified_by_its_class(
    first: object, second: object
) -> None:
    assert RecurringMessage.every(60, first).id == RecurringMessage.every(60, second).id


def test_messages_differing_only_outside_their_repr_have_different_ids() -> None:
    first = RecurringMessage.every("1 hour", RotateToken("acme", "token-A"))
    second = RecurringMessage.every("1 hour", RotateToken("acme", "token-B"))

    schedule = Schedule(first, second)

    assert first.id != second.id
    assert len(schedule.recurring_messages) == 2


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


def test_a_redispatched_message_is_identified_by_the_message_it_carries() -> None:
    first = RecurringMessage.every(60, RedispatchMessage(Named("a"), "urgent"))
    again = RecurringMessage.every(60, RedispatchMessage(Named("a"), "urgent"))
    other = RecurringMessage.every(60, RedispatchMessage(Named("b"), "urgent"))
    elsewhere = RecurringMessage.every(60, RedispatchMessage(Named("a"), "reports"))

    assert first.id == again.id
    assert len({first.id, other.id, elsewhere.id}) == 3


def test_a_redispatched_envelope_is_identified_by_its_stamps_too() -> None:
    bare = RecurringMessage.every(60, RedispatchMessage(Envelope(Named("a"))))
    stamped = RecurringMessage.every(
        60, RedispatchMessage(Envelope(Named("a"), (TransportNamesStamp(("reports",)),)))
    )

    assert bare.id != stamped.id


def test_a_message_with_no_plain_form_is_identified_by_its_class() -> None:
    first = RecurringMessage.every(60, _Opaque())
    again = RecurringMessage.every(60, _Opaque())
    other = RecurringMessage.every(60, _OtherOpaque())

    assert first.id == again.id
    assert first.id != other.id


class _Opaque:
    """A message the serializer has no plain form for."""


class _OtherOpaque:
    """Another one, of another class."""


def test_two_windows_of_one_message_are_two_recurring_messages() -> None:
    message = Plain()
    first = RecurringMessage.every("1 hour", message, until="2026-06-01T00:00:00+00:00")
    second = RecurringMessage.every("1 hour", message, until="2027-06-01T00:00:00+00:00")

    assert first.id != second.id
