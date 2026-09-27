"""What scheduled tasks call, by name."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_scheduler._built_services import BuiltServices
from xtr_scheduler.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Hashable

__all__ = ["TaskLocator"]


@final
class TaskLocator(ServiceProviderInterface[object]):
    """Hands over the objects scheduled tasks call, by the name tasks know them under.

    A task's name is the qualified name of the class or function it was
    declared on. Over objects already built, or over a container's locator
    that builds each one — with its dependencies — when first asked.
    """

    __slots__ = ("_targets",)

    def __init__(self, targets: Mapping[str, object] | ServiceProviderInterface[object]) -> None:
        """Hand over ``targets``, by name."""
        self._targets: ServiceProviderInterface[object] = (
            BuiltServices(targets, "task") if isinstance(targets, Mapping) else targets
        )

    @override
    async def get(self, name: Hashable, /) -> object:
        """Return the target named ``name``.

        Raises:
            InvalidArgumentError: If there is none.
        """
        if not self._targets.has(name):
            raise InvalidArgumentError(f'The task "{name}" is not found.')
        return await self._targets.get(name)

    @override
    def has(self, name: Hashable, /) -> bool:
        return self._targets.has(name)

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return self._targets.provided_services()
