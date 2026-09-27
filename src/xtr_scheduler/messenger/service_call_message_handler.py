"""Calls the task a :class:`ServiceCallMessage` names."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, cast, final

from xtr_messenger import as_message_handler

from xtr_scheduler.exception import InvalidArgumentError

from .service_call_message import ServiceCallMessage
from .task_locator import TaskLocator

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["ServiceCallMessageHandler"]

#: Stands for "no targets given": the ones declared in this process are used.
_DECLARED: Final = TaskLocator({})


@as_message_handler(ServiceCallMessage)
@final
class ServiceCallMessageHandler:
    """Looks the task target up, calls the method asked for, and returns what it returned.

    Built by a container, it is handed the container's task locator, so a
    target is built with its dependencies. Built with nothing, it calls the
    targets declared in this process, each built with no arguments.
    """

    __slots__ = ("_targets",)

    def __init__(self, targets: TaskLocator = _DECLARED) -> None:
        """Call the targets in ``targets`` — the declared ones when omitted."""
        self._targets = targets

    async def __call__(self, message: ServiceCallMessage) -> object:
        """Call ``message.method`` of the target named ``message.service``.

        Raises:
            InvalidArgumentError: If there is no such target or method.
        """
        target = await self._locator().get(message.service)
        call = target if message.method == "__call__" else getattr(target, message.method, None)
        if not callable(call):
            raise InvalidArgumentError(
                f'The task "{message.service}" has no method "{message.method}".'
            )
        result = call(*message.arguments)
        return await cast("Awaitable[object]", result) if inspect.isawaitable(result) else result

    def _locator(self) -> TaskLocator:
        if self._targets is _DECLARED:
            from xtr_scheduler.registry.declared_schedules import (  # noqa: PLC0415 — declarations are read when first needed
                declared_task_targets,
            )

            self._targets = declared_task_targets()
        return self._targets
