"""A task declared on a private method is refused where it is written."""

from __future__ import annotations

import pytest

from xtr_scheduler.decorator import as_cron_task
from xtr_scheduler.exception import SchedulerLogicError


def test_an_explicit_private_method_is_refused_at_declaration() -> None:
    def declare() -> type:
        @as_cron_task("0 3 * * *", method="_refresh")
        class Rates:
            async def _refresh(self) -> None: ...

        return Rates

    with pytest.raises(SchedulerLogicError, match='private method "_refresh"'):
        _ = declare()


def test_a_decorated_private_method_is_refused_at_declaration() -> None:
    def declare() -> type:
        class Maintenance:
            @as_cron_task("0 1 * * *")
            def _purge(self) -> None: ...

        return Maintenance

    with pytest.raises(SchedulerLogicError, match='private method "_purge"'):
        _ = declare()


def test_a_dunder_call_method_is_allowed() -> None:
    @as_cron_task("0 3 * * *", method="__call__")
    class Reports:
        def __call__(self) -> None: ...

    assert callable(Reports)
