"""The methods each scheduled task may be called through, by target name."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

__all__ = ["TaskMethods"]

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


@final
class TaskMethods:
    """The allow-list of methods per task target: what a message may ask for.

    A scheduled message crosses a transport, so it can name any method of a
    built service. The handler calls one only when it appears here, so a
    crafted message cannot reach a method no decorator declared. The bundle
    builds this from its kernel's own task declarations.
    """

    __slots__ = ("_methods",)

    def __init__(self, methods: Mapping[str, Collection[str]]) -> None:
        """Allow each target the methods ``methods`` lists under its name."""
        self._methods = methods

    def allowed(self, name: str) -> Collection[str]:
        """Return the methods target ``name`` may be called through; none when unknown."""
        return self._methods.get(name, ())
