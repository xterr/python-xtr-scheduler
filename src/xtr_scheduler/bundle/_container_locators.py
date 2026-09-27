"""Schedule providers and task targets, built by a container when first asked for."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import bind_callable
from xtr_service_contracts import ServiceProviderInterface

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.registry.schedule_with_tasks import ScheduleWithTasks
from xtr_scheduler.schedule import Schedule

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping

    from xtr_service_contracts import ContainerInterface

    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

    from ._declared import Declared

__all__ = ["ContainerSchedules", "ContainerTargets"]


@final
class ContainerSchedules(ServiceProviderInterface["ScheduleProviderInterface"]):
    """Each declared schedule, its provider built by the container, its tasks joined to it.

    Built once per name: the transport consuming a schedule and the listener
    announcing its runs must see the same schedule, listeners and all.
    """

    __slots__ = ("_built", "_container", "_declared")

    def __init__(self, container: ContainerInterface, declared: Declared) -> None:
        """Build the schedules ``declared`` names, from ``container``."""
        self._container = container
        self._declared = declared
        self._built: dict[str, ScheduleProviderInterface] = {}

    @override
    async def get(self, name: Hashable, /) -> ScheduleProviderInterface:
        """Return the provider of the schedule ``name``, building it the first time.

        Raises:
            InvalidArgumentError: If no such schedule was declared.
        """
        key = str(name)
        built = self._built.get(key)
        if built is not None:
            return built
        if not self.has(key):
            raise InvalidArgumentError(f'The schedule "{key}" is not found.')
        tasks = self._declared.recurring_messages(key)
        provider_class = self._declared.providers.get(key)
        if provider_class is None:
            built = Schedule(*tasks)
        else:
            inner = cast("ScheduleProviderInterface", await self._container.get(provider_class))
            built = ScheduleWithTasks(inner, tasks) if tasks else inner
        self._built[key] = built
        return built

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._declared.names()

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType(
            {name: self._declared.providers.get(name, Schedule) for name in self._declared.names()}
        )


@final
class ContainerTargets(ServiceProviderInterface[object]):
    """Each task target: a class built by the container, a function with its services bound."""

    __slots__ = ("_bound", "_container", "_declared")

    def __init__(self, container: ContainerInterface, declared: Declared) -> None:
        """Hand over the targets ``declared`` names, from ``container``."""
        self._container = container
        self._declared = declared
        self._bound: dict[str, Callable[..., object]] = {}

    @override
    async def get(self, name: Hashable, /) -> object:
        """Return the target named ``name``.

        Raises:
            InvalidArgumentError: If no such target was declared.
        """
        key = str(name)
        target_class = self._declared.task_classes.get(key)
        if target_class is not None:
            return await self._container.get(target_class)
        function = self._declared.functions.get(key)
        if function is None:
            raise InvalidArgumentError(f'The task "{key}" is not found.')
        bound = self._bound.get(key)
        if bound is None:
            bound = bind_callable(self._container, cast("Callable[..., object]", function))
            self._bound[key] = bound
        return bound

    @override
    def has(self, name: Hashable, /) -> bool:
        key = str(name)
        return key in self._declared.task_classes or key in self._declared.functions

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        functions = self._declared.functions.items()
        entries: list[tuple[Hashable, type[object]]] = [
            *self._declared.task_classes.items(),
            *((name, type(function)) for name, function in functions),
        ]
        return MappingProxyType(dict(entries))
