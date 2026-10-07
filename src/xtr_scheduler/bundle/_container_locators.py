"""Schedule providers and task targets, resolved through locators, never the container.

A schedule provider is a service the container builds; a class task target is
too. Both are reached by name through a
:class:`~xtr_dependency_injection.ServiceLocator` the bundle builds once it has
its container — a lazy, name-keyed view that builds each entry only when it is
asked for. A function task target is not a service: the bundle binds it to the
container ahead of time and hands the bound callables over by name.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.registry.schedule_with_tasks import ScheduleWithTasks
from xtr_scheduler.schedule import Schedule

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping

    from xtr_dependency_injection import ServiceLocator

    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

    from ._declared import Declared

__all__ = ["ContainerSchedules", "ContainerTargets"]


@final
class ContainerSchedules(ServiceProviderInterface["ScheduleProviderInterface"]):
    """Each declared schedule, its provider built by the container, its tasks joined to it.

    Built once per name: the transport consuming a schedule and the listener
    announcing its runs must see the same schedule, listeners and all.
    """

    __slots__ = ("_built", "_declared", "_providers")

    def __init__(
        self, providers: ServiceLocator[ScheduleProviderInterface], declared: Declared
    ) -> None:
        """Build the schedules ``declared`` names, their providers from ``providers``."""
        self._providers = providers
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
        if key in self._declared.providers:
            inner = await self._providers.get(key)
            built = ScheduleWithTasks(inner, tasks) if tasks else inner
        else:
            built = Schedule(*tasks)
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
    """Each task target: a class built by the container, a function bound to it."""

    __slots__ = ("_classes", "_declared", "_functions")

    def __init__(
        self,
        classes: ServiceLocator[object],
        functions: Mapping[str, Callable[..., object]],
        declared: Declared,
    ) -> None:
        """Hand over the class targets in ``classes`` and the bound ``functions``, by name."""
        self._classes = classes
        self._functions = functions
        self._declared = declared

    @override
    async def get(self, name: Hashable, /) -> object:
        """Return the target named ``name``.

        Raises:
            InvalidArgumentError: If no such target was declared.
        """
        key = str(name)
        if self._classes.has(key):
            return await self._classes.get(key)
        bound = self._functions.get(key)
        if bound is None:
            raise InvalidArgumentError(f'The task "{key}" is not found.')
        return bound

    @override
    def has(self, name: Hashable, /) -> bool:
        key = str(name)
        return self._classes.has(key) or key in self._functions

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        entries: dict[Hashable, type[object]] = {
            **self._declared.task_classes,
            **{name: type(function) for name, function in self._declared.functions.items()},
        }
        return MappingProxyType(entries)
