"""Services already built, handed over by name."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, TypeVar, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

__all__ = ["BuiltServices"]

_T = TypeVar("_T")


@final
class BuiltServices(ServiceProviderInterface[_T], Generic[_T]):
    """Hands over services from a mapping — the locator for code with no container."""

    __slots__ = ("_services", "_what")

    def __init__(self, services: Mapping[str, _T], what: str) -> None:
        """Hand over ``services``; ``what`` names them in the error for a missing one."""
        self._services = dict(services)
        self._what = what

    @override
    async def get(self, name: Hashable, /) -> _T:
        """Return the service ``name``.

        Raises:
            InvalidArgumentError: If there is none.
        """
        service = self._services.get(str(name))
        if service is None:
            raise InvalidArgumentError(f'The {self._what} "{name}" is not found.')
        return service

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._services

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType({name: type(s) for name, s in self._services.items()})
