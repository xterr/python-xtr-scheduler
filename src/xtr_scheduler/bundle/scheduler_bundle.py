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
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    named_factory,
    optional_service,
    required_bundle,
)
from xtr_messenger import TransportFactoryInterface
from xtr_messenger.bundle import TRANSPORT_FACTORY_TAG, MessengerBundle
from xtr_service_contracts import ContainerInterface

from xtr_scheduler.event_listener.dispatch_scheduler_event_listener import (
    DispatchSchedulerEventListener,
)
from xtr_scheduler.messenger.scheduler_transport_factory import SchedulerTransportFactory
from xtr_scheduler.messenger.task_locator import TaskLocator
from xtr_scheduler.registry.declarations import schedules_declared_on, tasks_declared_on
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
            AddScheduleMessengerPass(declared), stage=PassStage.BEFORE_OPTIMIZATION, priority=0
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
        _ = services.set(named_factory(_schedule_locator(self._declared), "scheduler_schedules"))
        _ = services.set(named_factory(_task_locator(self._declared), "scheduler_tasks"))
        services.load("xtr_scheduler.messenger.service_call_message_handler")
        _ = services.set(_scheduler_transport_factory, qualifier=_TRANSPORT_FACTORY).add_tag(
            TRANSPORT_FACTORY_TAG
        )
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


def _schedule_locator(
    declared: Declared,
) -> Callable[[ContainerInterface], Coroutine[None, None, ScheduleProviderLocator]]:
    async def build(container: ContainerInterface) -> ScheduleProviderLocator:
        return ScheduleProviderLocator(ContainerSchedules(container, declared))

    return build


def _task_locator(
    declared: Declared,
) -> Callable[[ContainerInterface], Coroutine[None, None, TaskLocator]]:
    async def build(container: ContainerInterface) -> TaskLocator:
        return TaskLocator(ContainerTargets(container, declared))

    return build


async def _scheduler_transport_factory(
    schedules: ScheduleProviderLocator,
    config: SchedulerConfig,
    container: ContainerInterface,
) -> SchedulerTransportFactory:
    """Serve ``schedule://`` DSNs an application configures, from the container's schedules."""
    return SchedulerTransportFactory(
        schedules,
        clock=await optional_service(container, ClockInterface),
        use_messenger_routing=config.use_messenger_routing,
    )
