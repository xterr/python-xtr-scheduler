"""Registers a consumable receiver for every schedule a kernel declares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_clock import ClockInterface
from xtr_dependency_injection import (
    Definition,
    Origin,
    named_factory,
    optional_service,
)
from xtr_messenger import MessageBusConfig
from xtr_messenger.bundle import RECEIVER_TAG
from xtr_service_contracts import ContainerInterface

from xtr_scheduler.messenger._located_message_generator import LocatedMessageGenerator
from xtr_scheduler.messenger.scheduler_transport import SchedulerTransport
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from .scheduler_config import SchedulerConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from xtr_dependency_injection import ContainerBuilder

    from ._declared import Declared

__all__ = ["AddScheduleMessengerPass"]

_ORIGIN: Final = Origin("bundle", "scheduler")


@final
class AddScheduleMessengerPass:
    """Makes ``scheduler_<name>`` consumable for every declared schedule.

    Runs after autoconfiguration has found every schedule and task — the
    early scan's and the late scans' alike — and before the messenger bundle
    collects the receivers workers can consume. A name the application
    already configured as a transport, or registered as a receiver, is left
    to it: that is how an application overrides one.
    """

    __slots__ = ("_declared",)

    def __init__(self, declared: Declared) -> None:
        """Register receivers for what ``declared`` holds."""
        self._declared = declared

    def process(self, builder: ContainerBuilder) -> None:
        """Register a receiver per schedule, unless one is already there."""
        config = builder.get_extension_config(MessageBusConfig)
        taken = set(config.transports)
        for tags in builder.find_tagged_service_ids(RECEIVER_TAG).values():
            taken.update(str(tag.get("alias")) for tag in tags)
        for name in self._declared.names():
            transport = f"scheduler_{name}"
            if transport in taken:
                continue
            definition = Definition(
                (SchedulerTransport, transport),
                named_factory(_transport_factory(name, transport), f"scheduler_transport_{name}"),
                "factory",
                "singleton",
                _ORIGIN,
            )
            _ = builder.set_definition(definition).add_tag(RECEIVER_TAG, alias=transport)


def _transport_factory(
    name: str, transport: str
) -> Callable[..., Coroutine[None, None, SchedulerTransport]]:
    """Return a factory building the transport ``transport`` for the schedule ``name``."""

    async def build(
        schedules: ScheduleProviderLocator,
        config: SchedulerConfig,
        container: ContainerInterface,
    ) -> SchedulerTransport:
        clock = await optional_service(container, ClockInterface)
        return SchedulerTransport(
            LocatedMessageGenerator(schedules, name, clock),
            name=transport,
            use_messenger_routing=config.use_messenger_routing,
            clock=clock,
        )

    return build
