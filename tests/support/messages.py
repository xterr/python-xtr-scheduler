"""Messages scheduled in the tests."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override
from xtr_messenger import as_message


@as_message
@dataclass(frozen=True, slots=True)
class Named:
    """A message told apart by its name, with a string form of its own."""

    name: str

    @override
    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Plain:
    """A message with no string form of its own."""

    value: int = 0
