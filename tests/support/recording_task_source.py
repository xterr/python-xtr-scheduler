"""A source of task targets that builds each one on request and records every build."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping


@final
class RecordingTaskSource(ServiceProviderInterface[object]):
    """Knows one target, builds it on every :meth:`get`, and appends the name to :attr:`built`."""

    def __init__(self, known: str, target: type[object]) -> None:
        self._known = known
        self._target = target
        self.built: list[str] = []

    @override
    async def get(self, name: Hashable, /) -> object:
        self.built.append(str(name))
        return self._target()

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) == self._known

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType({self._known: self._target})
