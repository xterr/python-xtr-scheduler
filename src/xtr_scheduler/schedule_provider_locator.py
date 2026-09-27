"""Schedule providers by name."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from ._built_services import BuiltServices
from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Hashable

    from .schedule_provider_interface import ScheduleProviderInterface

__all__ = ["ScheduleProviderLocator"]


@final
class ScheduleProviderLocator(ServiceProviderInterface["ScheduleProviderInterface"]):
    """Hands over schedule providers by the name of their schedule.

    Over providers already built, or over a container's locator that builds
    each one when first asked — the transport, the event listener and the
    debug command all read schedules through this, whichever it is.
    """

    __slots__ = ("_providers",)

    def __init__(
        self,
        providers: Mapping[str, ScheduleProviderInterface]
        | ServiceProviderInterface[ScheduleProviderInterface],
    ) -> None:
        """Hand over ``providers``, by name."""
        self._providers: ServiceProviderInterface[ScheduleProviderInterface] = (
            BuiltServices(providers, "schedule") if isinstance(providers, Mapping) else providers
        )

    @override
    async def get(self, name: Hashable, /) -> ScheduleProviderInterface:
        """Return the provider of the schedule ``name``.

        Raises:
            InvalidArgumentError: If there is none.
        """
        if not self._providers.has(name):
            raise InvalidArgumentError(f'The schedule "{name}" is not found.')
        return await self._providers.get(name)

    @override
    def has(self, name: Hashable, /) -> bool:
        return self._providers.has(name)

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return self._providers.provided_services()

    def names(self) -> tuple[str, ...]:
        """Return the name of every schedule, in the order they were registered."""
        return tuple(str(name) for name in self.provided_services())
