"""The declared schedules and task targets, for an application with no container."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.messenger.task_locator import TaskLocator
from xtr_scheduler.schedule import Schedule
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from .declarations import (
    declared_schedule_class,
    declared_schedule_names,
    declared_tasks,
    task_name,
)
from .schedule_with_tasks import ScheduleWithTasks

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Iterable, Mapping

    from xtr_scheduler.recurring_message import RecurringMessage
    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

    from .task_declaration import TaskDeclaration

__all__ = [
    "declared_schedules",
    "declared_task_methods",
    "declared_task_targets",
    "schedule_of",
]


def schedule_of(
    provider: ScheduleProviderInterface | None,
    tasks: Iterable[tuple[str, TaskDeclaration]],
) -> ScheduleProviderInterface:
    """Join ``tasks`` to ``provider``'s schedule, or give them a schedule of their own.

    ``tasks`` pairs each declaration with the name of the target it calls.
    """
    recurring: list[RecurringMessage] = [
        declaration.recurring_message(target) for target, declaration in tasks
    ]
    if provider is None:
        return Schedule(*recurring)
    return ScheduleWithTasks(provider, recurring) if recurring else provider


def declared_schedules() -> ScheduleProviderLocator:
    """Return the schedules declared in this process.

    Each is built the first time it is asked for — its provider with no
    arguments — so a schedule this process never runs is never built.
    """
    return ScheduleProviderLocator(_DeclaredSchedules())


def declared_task_targets() -> TaskLocator:
    """Return the task targets declared in this process, each class built when first called."""
    return TaskLocator(_DeclaredTargets())


def declared_task_methods() -> dict[str, frozenset[str]]:
    """Return the methods each task target was declared to be called through, by target name.

    A target declared with no ``method`` is called through ``__call__``. The
    handler calls a target through nothing else, so a crafted message cannot
    reach a method no decorator named.
    """
    methods: dict[str, set[str]] = {}
    for target, declaration in declared_tasks():
        methods.setdefault(task_name(target), set()).add(declaration.method or "__call__")
    return {name: frozenset(allowed) for name, allowed in methods.items()}


@final
class _DeclaredSchedules(ServiceProviderInterface["ScheduleProviderInterface"]):
    """The schedules declared in this process, built one at a time, once each."""

    __slots__ = ("_built",)

    def __init__(self) -> None:
        self._built: dict[str, ScheduleProviderInterface] = {}

    @override
    async def get(self, name: Hashable, /) -> ScheduleProviderInterface:
        key = str(name)
        built = self._built.get(key)
        if built is None:
            if key not in declared_schedule_names():
                raise InvalidArgumentError(f'The schedule "{key}" is not found.')
            provider_class = declared_schedule_class(key)
            provider = (
                None
                if provider_class is None
                else cast("ScheduleProviderInterface", provider_class())
            )
            tasks = (
                (task_name(target), declaration)
                for target, declaration in declared_tasks()
                if declaration.schedule == key
            )
            built = self._built[key] = schedule_of(provider, tasks)
        return built

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in declared_schedule_names()

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType(
            {name: declared_schedule_class(name) or Schedule for name in declared_schedule_names()}
        )


@final
class _DeclaredTargets(ServiceProviderInterface[object]):
    """The task targets declared in this process: classes built on first call, once each."""

    __slots__ = ("_built",)

    def __init__(self) -> None:
        self._built: dict[str, object] = {}

    @override
    async def get(self, name: Hashable, /) -> object:
        key = str(name)
        if key in self._built:
            return self._built[key]
        target = self._targets().get(key)
        if target is None:
            raise InvalidArgumentError(f'The task "{key}" is not found.')
        built = cast("Callable[[], object]", target)() if isinstance(target, type) else target
        self._built[key] = built
        return built

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._targets()

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType(
            {
                name: target if isinstance(target, type) else type(target)
                for name, target in self._targets().items()
            }
        )

    @staticmethod
    def _targets() -> dict[str, object]:
        return {task_name(target): target for target, _declaration in declared_tasks()}
