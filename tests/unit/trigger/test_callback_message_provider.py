"""Messages a function decides on at each run."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.contexts import a_context
from xtr_scheduler.trigger import CallbackMessageProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from xtr_scheduler.generator import MessageContext
    from xtr_scheduler.trigger.callback_message_provider import Produced

pytestmark = pytest.mark.anyio


def _named(context: MessageContext) -> list[str]:
    return [f"{context.name}:1", f"{context.name}:2"]


async def _later(context: MessageContext) -> list[str]:
    return [context.id]


async def _streamed(context: MessageContext) -> AsyncIterator[str]:
    yield context.name
    yield context.id


@pytest.mark.parametrize(
    ("callback", "expected"),
    [(_named, ["tenants:1", "tenants:2"]), (_later, ["abc"]), (_streamed, ["tenants", "abc"])],
)
async def test_it_takes_messages_from_a_function_a_coroutine_or_an_async_generator(
    callback: Callable[[MessageContext], Produced], expected: list[str]
) -> None:
    provider = CallbackMessageProvider(callback, "id1")

    messages = [message async for message in provider.get_messages(a_context("tenants"))]

    assert messages == expected


def test_it_is_described_by_its_description_or_else_its_id() -> None:
    assert str(CallbackMessageProvider(_named, "id1", "per tenant")) == "per tenant"
    assert str(CallbackMessageProvider(_named, "id1")) == "id1"
