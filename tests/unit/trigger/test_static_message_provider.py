"""The same messages on every run."""

from __future__ import annotations

import pytest

from tests.support.contexts import a_context
from xtr_scheduler.trigger import StaticMessageProvider

pytestmark = pytest.mark.anyio


async def test_it_yields_its_messages_on_every_run() -> None:
    provider = StaticMessageProvider(["a", "b"], "id1")

    first = [message async for message in provider.get_messages(a_context())]
    second = [message async for message in provider.get_messages(a_context())]

    assert first == second == ["a", "b"]


def test_it_is_described_by_its_description_or_else_its_id() -> None:
    assert str(StaticMessageProvider([], "id1", "a ping")) == "a ping"
    assert str(StaticMessageProvider([], "id1")) == "id1"
    assert StaticMessageProvider([], "id1").id == "id1"
