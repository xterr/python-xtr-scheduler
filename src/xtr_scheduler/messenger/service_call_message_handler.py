"""Calls the task a :class:`ServiceCallMessage` names."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

from xtr_messenger import as_message_handler

from xtr_scheduler.exception import InvalidArgumentError

from .service_call_message import ServiceCallMessage
from .task_locator import TaskLocator
from .task_methods import TaskMethods

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["ServiceCallMessageHandler"]


@as_message_handler(ServiceCallMessage)
@final
class ServiceCallMessageHandler:
    """Looks the task target up, calls the method asked for, and returns what it returned.

    It is handed a :class:`TaskLocator` over the task targets — built by the
    container with their dependencies — and a :class:`TaskMethods` allow-list.
    A message may name only a method a decorator declared for its target, and
    never a private or dunder name: a call crossing a transport from another
    worker cannot reach an arbitrary attribute of a built service. Both are
    checked before the target is looked up, so a call this refuses never
    builds one.
    """

    __slots__ = ("_methods", "_targets")

    def __init__(self, targets: TaskLocator, methods: TaskMethods) -> None:
        """Call the targets in ``targets``, each through the methods ``methods`` allows."""
        self._targets = targets
        self._methods = methods

    async def __call__(self, message: ServiceCallMessage) -> object:
        """Call ``message.method`` of the target named ``message.service``.

        Raises:
            InvalidArgumentError: If there is no such target, or the method
                was not declared for it, or its name is private.
        """
        method = message.method
        if method != "__call__" and method.startswith("_"):
            raise InvalidArgumentError(
                f'The task "{message.service}" refuses the private method "{method}".'
            )
        if not self._targets.has(message.service):
            raise InvalidArgumentError(f'The task "{message.service}" is not found.')
        if method not in self._methods.allowed(message.service):
            raise InvalidArgumentError(
                f'The task "{message.service}" did not declare the method "{method}".'
            )
        target = await self._targets.get(message.service)
        call = target if method == "__call__" else getattr(target, method, None)
        if not callable(call):
            raise InvalidArgumentError(f'The task "{message.service}" has no method "{method}".')
        result = call(*message.arguments)
        return await cast("Awaitable[object]", result) if inspect.isawaitable(result) else result
