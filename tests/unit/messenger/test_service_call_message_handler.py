"""Calls the task a :class:`ServiceCallMessage` names."""

from __future__ import annotations

import re
from typing import final

import pytest

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.messenger import ServiceCallMessage, ServiceCallMessageHandler, TaskLocator

pytestmark = pytest.mark.anyio


@final
class Reports:
    """A task target with a sync call and an async method."""

    def __call__(self, region: str) -> str:
        return f"all {region}"

    async def nightly(self, region: str, days: int) -> str:
        return f"{region} for {days} days"


def handler() -> ServiceCallMessageHandler:
    return ServiceCallMessageHandler(TaskLocator({"app.Reports": Reports()}))


async def test_it_calls_the_target_itself_and_returns_what_it_returned() -> None:
    assert await handler()(ServiceCallMessage("app.Reports", arguments=("eu",))) == "all eu"


async def test_it_calls_and_awaits_the_method_asked_for() -> None:
    message = ServiceCallMessage("app.Reports", "nightly", ("eu", 3))

    assert await handler()(message) == "eu for 3 days"


async def test_a_target_it_does_not_know_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape('The task "app.Nope" is not found')):
        _ = await handler()(ServiceCallMessage("app.Nope"))


async def test_a_method_the_target_does_not_have_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='has no method "weekly"'):
        _ = await handler()(ServiceCallMessage("app.Reports", "weekly"))
