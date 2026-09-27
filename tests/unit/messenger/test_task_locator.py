"""What scheduled tasks call, by name."""

from __future__ import annotations

import re

import pytest

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.messenger import TaskLocator

pytestmark = pytest.mark.anyio


async def test_it_hands_over_targets_by_name() -> None:
    target = object()
    locator = TaskLocator({"app.Job": target})

    assert locator.has("app.Job")
    assert await locator.get("app.Job") is target
    assert dict(locator.provided_services()) == {"app.Job": object}


async def test_it_wraps_another_locator() -> None:
    target = object()
    locator = TaskLocator(TaskLocator({"app.Job": target}))

    assert await locator.get("app.Job") is target


async def test_an_unknown_target_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape('The task "app.Nope" is not found')):
        _ = await TaskLocator({}).get("app.Nope")
