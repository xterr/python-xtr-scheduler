"""Calls the task a :class:`ServiceCallMessage` names."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast, final

import pytest

from tests.support.recording_task_source import RecordingTaskSource
from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.messenger import (
    ServiceCallMessage,
    ServiceCallMessageHandler,
    TaskLocator,
    TaskMethods,
)

pytestmark = pytest.mark.anyio

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Reports:
    """A task target with a sync call and an async method."""

    def __call__(self, region: str) -> str:
        return f"all {region}"

    async def nightly(self, region: str, days: int) -> str:
        return f"{region} for {days} days"


def handler() -> ServiceCallMessageHandler:
    return ServiceCallMessageHandler(
        TaskLocator({"app.Reports": Reports()}),
        TaskMethods({"app.Reports": {"__call__", "nightly"}}),
    )


def over(source: RecordingTaskSource) -> ServiceCallMessageHandler:
    methods = TaskMethods({"app.Reports": {"__call__"}})
    return ServiceCallMessageHandler(TaskLocator(source), methods)


async def test_it_calls_the_target_itself_and_returns_what_it_returned() -> None:
    assert await handler()(ServiceCallMessage("app.Reports", arguments=("eu",))) == "all eu"


async def test_it_calls_and_awaits_the_method_asked_for() -> None:
    message = ServiceCallMessage("app.Reports", "nightly", ("eu", 3))

    assert await handler()(message) == "eu for 3 days"


async def test_a_target_it_does_not_know_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape('The task "app.Nope" is not found')):
        _ = await handler()(ServiceCallMessage("app.Nope"))


async def test_an_undeclared_method_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='did not declare the method "weekly"'):
        _ = await handler()(ServiceCallMessage("app.Reports", "weekly"))


async def test_a_dunder_method_is_refused() -> None:
    message = ServiceCallMessage("app.Reports", "__reduce__")
    pattern = re.escape('refuses the private method "__reduce__"')

    with pytest.raises(InvalidArgumentError, match=pattern):
        _ = await handler()(message)


async def test_a_declared_method_absent_from_the_target_is_refused() -> None:
    scoped = ServiceCallMessageHandler(
        TaskLocator({"app.Reports": Reports()}), TaskMethods({"app.Reports": {"gone"}})
    )

    with pytest.raises(InvalidArgumentError, match='has no method "gone"'):
        _ = await scoped(ServiceCallMessage("app.Reports", "gone"))


async def test_an_undeclared_method_is_refused_before_the_target_is_built() -> None:
    source = RecordingTaskSource("app.Reports", Reports)

    with pytest.raises(InvalidArgumentError, match='did not declare the method "weekly"'):
        _ = await over(source)(ServiceCallMessage("app.Reports", "weekly"))

    assert source.built == []


async def test_a_declared_method_is_called_on_the_target_the_locator_builds() -> None:
    source = RecordingTaskSource("app.Reports", Reports)

    result = await over(source)(ServiceCallMessage("app.Reports", arguments=("eu",)))

    assert result == "all eu"
    assert source.built == ["app.Reports"]


def test_the_handler_requires_its_targets_and_methods() -> None:
    construct = cast("Callable[..., object]", ServiceCallMessageHandler)
    with pytest.raises(TypeError):
        _ = construct()
