"""The xtr-scheduler bundle: declared schedules and tasks, consumable by messenger workers.

An application listing :class:`SchedulerBundle` — which brings
``MessengerBundle`` with it — gets every class declared with
``@as_schedule`` and every ``@as_cron_task`` / ``@as_periodic_task`` its scan
finds, built by the container with their dependencies, and each schedule
consumable as ``scheduler_<name>`` — run it with ``messenger:consume
scheduler_default``. With the event dispatcher bundle active, every run is
announced; with the console bundle, ``debug:scheduler`` lists what runs next;
with the cache bundle, a ``scheduler`` pool is there for schedules to keep
their state in.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    ServiceLocator,
    as_bundle,
    bind_callable,
    bundle_active,
    named_factory,
    optional_service,
    required_bundle,
)
from xtr_messenger import TransportFactoryInterface
from xtr_messenger.bundle import TRANSPORT_FACTORY_TAG, MessengerBundle

from xtr_scheduler.event_listener.dispatch_scheduler_event_listener import (
    DispatchSchedulerEventListener,
)
from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.messenger.scheduler_transport_factory import SchedulerTransportFactory
from xtr_scheduler.messenger.task_locator import TaskLocator
from xtr_scheduler.messenger.task_methods import TaskMethods
from xtr_scheduler.registry.declarations import schedules_declared_on, tasks_declared_on
from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from ._add_schedule_messenger_pass import AddScheduleMessengerPass
from ._container_locators import ContainerSchedules, ContainerTargets
from ._declared import Declared
from .scheduler_config import SchedulerConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from xtr_scheduler.registry.task_declaration import TaskDeclaration

__all__ = ["SCHEDULER_POOL", "SchedulerBundle"]

_TRANSPORT_FACTORY: str = "xtr_scheduler.schedule"

_NO_CONTAINER: Final = "the scheduler bundle has no container; it is used before it booted"

SCHEDULER_POOL: Final = "scheduler"
"""The cache pool added for schedules' saved state, when the cache bundle is active."""


def _add_scheduler_pool(config: object) -> object:
    """Add the ``scheduler`` pool to the cache config — on the app pool's adapter.

    A pool of its own keeps checkpoints apart from the application's values,
    under a namespace of their own, and clearable on their own. One the
    application configured under that name is left as it is.
    """
    from xtr_cache.bundle import (  # noqa: PLC0415 — the cache bundle is active, so xtr-cache is installed
        CacheConfig,
        PoolConfig,
    )

    if not isinstance(config, CacheConfig) or SCHEDULER_POOL in config.pools:
        return config
    return replace(config, pools={SCHEDULER_POOL: PoolConfig(), **config.pools})


@final
@required_bundle(MessengerBundle)
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("scheduler", config=SchedulerConfig)
class SchedulerBundle(Bundle[SchedulerConfig]):
    """Wires declared schedules and tasks to the container and to messenger workers."""

    def __init__(self) -> None:
        """Start with nothing declared."""
        self._declared = Declared()

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """When the cache bundle is active, add a ``scheduler`` pool to its config.

        Nothing uses it on its own: a schedule provider asks for it —
        ``Annotated[CacheInterface, Target("scheduler")]`` — and hands it to
        :meth:`Schedule.stateful <xtr_scheduler.schedule.Schedule.stateful>`.
        """
        if bundle_active(builder, "cache"):
            builder.prepend_extension_config("cache", _add_scheduler_pool)

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Collect declared schedules and tasks; register the pass that makes them consumable.

        A task declared for other environments (``env=``) is left out, the
        way ``@when`` leaves out a service — but its schedule stays, empty if
        nothing else is on it, so a worker can be started for it anywhere.
        """
        declared = self._declared
        environment = str(builder.get_parameter("kernel.environment"))

        def register_schedule(obj: object, name: str, services: ServiceConfigurator) -> None:
            if isinstance(obj, type):
                declared.add_provider(name, obj)
                _ = services.set(obj)

        def register_task(
            obj: object, declaration: TaskDeclaration, services: ServiceConfigurator
        ) -> None:
            if not declaration.exists_in(environment):
                declared.add_schedule(declaration.schedule)
                return
            declared.add_task(obj, declaration)
            if isinstance(obj, type):
                _ = services.set(obj)

        builder.register_attribute_for_autoconfiguration(schedules_declared_on, register_schedule)
        builder.register_attribute_for_autoconfiguration(tasks_declared_on, register_task)
        builder.add_compiler_pass(
            AddScheduleMessengerPass(declared, self._resolve_clock),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=0,
        )

    @override
    def load_extension(
        self,
        config: SchedulerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the locators, and what the active peers can use them for."""
        del config
        declared = self._declared
        _ = services.set(named_factory(_schedule_locator(self, declared), "scheduler_schedules"))
        _ = services.set(named_factory(_task_locator(self, declared), "scheduler_tasks"))
        _ = services.set(named_factory(_task_methods(declared), "scheduler_task_methods"))
        services.load("xtr_scheduler.messenger.service_call_message_handler")
        _ = services.set(
            _scheduler_transport_factory(self._resolve_clock), qualifier=_TRANSPORT_FACTORY
        ).add_tag(TRANSPORT_FACTORY_TAG)
        services.alias(
            TransportFactoryInterface,
            SchedulerTransportFactory,
            alias_qualifier=_TRANSPORT_FACTORY,
            target_qualifier=_TRANSPORT_FACTORY,
        )
        if bundle_active(builder, "event_dispatcher"):
            _ = services.set(DispatchSchedulerEventListener)
        if bundle_active(builder, "console"):
            services.load("xtr_scheduler.command")

    async def _resolve_clock(self) -> ClockInterface | None:
        """Return the container's clock, or ``None`` when no clock bundle is active."""
        container = self.container
        if container is None:
            raise SchedulerLogicError(_NO_CONTAINER)
        return await optional_service(container, ClockInterface)


def _schedule_locator(
    bundle: SchedulerBundle, declared: Declared
) -> Callable[[], Coroutine[None, None, ScheduleProviderLocator]]:
    """Return a factory serving the container's schedules through a :class:`ServiceLocator`."""

    async def build() -> ScheduleProviderLocator:
        container = bundle.container
        if container is None:
            raise SchedulerLogicError(_NO_CONTAINER)
        providers = ServiceLocator[ScheduleProviderInterface](
            container, {name: (cls, None) for name, cls in declared.providers.items()}
        )
        return ScheduleProviderLocator(ContainerSchedules(providers, declared))

    return build


def _task_locator(
    bundle: SchedulerBundle, declared: Declared
) -> Callable[[], Coroutine[None, None, TaskLocator]]:
    """Return a factory serving the task targets: classes by locator, functions bound."""

    async def build() -> TaskLocator:
        container = bundle.container
        if container is None:
            raise SchedulerLogicError(_NO_CONTAINER)
        classes = ServiceLocator[object](
            container, {name: (cls, None) for name, cls in declared.task_classes.items()}
        )
        functions = {
            name: bind_callable(container, cast("Callable[..., object]", function))
            for name, function in declared.functions.items()
        }
        return TaskLocator(ContainerTargets(classes, functions, declared))

    return build


def _task_methods(declared: Declared) -> Callable[[], TaskMethods]:
    """Return a factory building the method allow-list from the kernel's declarations."""

    def build() -> TaskMethods:
        return TaskMethods(declared.task_methods())

    return build


def _scheduler_transport_factory(
    clock_source: Callable[[], Coroutine[None, None, ClockInterface | None]],
) -> Callable[..., Coroutine[None, None, SchedulerTransportFactory]]:
    """Return a factory building the ``schedule://`` transport factory, clock and all."""

    async def build(
        schedules: ScheduleProviderLocator, config: SchedulerConfig
    ) -> SchedulerTransportFactory:
        return SchedulerTransportFactory(
            schedules,
            clock=await clock_source(),
            use_messenger_routing=config.use_messenger_routing,
        )

    return build
