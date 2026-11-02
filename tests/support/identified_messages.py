"""Messages whose ``repr`` does not tell them apart, or differs from one process to the next.

Then ordinary messages the serializer refuses to write exactly — each pair holding different
data — and messages holding a value nothing can write.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, final
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from pydantic_core import core_schema
from typing_extensions import override
from xtr_messenger import as_message

if TYPE_CHECKING:
    from threading import Event  # noqa: TC004 — unresolvable at runtime is what Signal is for

    from pydantic import GetCoreSchemaHandler

#: Resources whose names a set hands out in an order that changes with the hash seed.
RESOURCES = frozenset({"cpu", "memory", "disk", "network", "gpu", "storage", "requests"})


@as_message(name="probe.quotas.v1")
@dataclass(frozen=True)
class Quotas:
    """A dict whose key order, and so its ``repr``, follows the set it was built from."""

    limits: dict[str, int]


@final
class Sku:
    """A value object with no ``repr`` of its own: the default one shows its address."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sku) and other.code == self.code

    @override
    def __hash__(self) -> int:
        return hash(self.code)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        del source, handler
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(cls, core_schema.str_schema()),
            python_schema=core_schema.is_instance_schema(cls),
            serialization=core_schema.plain_serializer_function_ser_schema(
                _code, return_schema=core_schema.str_schema()
            ),
        )


def _code(sku: Sku) -> str:
    return sku.code


class Restock(BaseModel):
    """A model holding a value object whose ``repr`` is its address."""

    sku: Sku
    quantity: int


@dataclass(frozen=True)
class RotateToken:
    """A message keeping its secret out of its ``repr``."""

    tenant: str
    token: str = field(repr=False)


def quotas() -> Quotas:
    """Return quotas built by walking a set, as an application might."""
    return Quotas({name: len(name) for name in set(RESOURCES)})


def restock() -> Restock:
    """Return a restock of a fresh value object."""
    return Restock(sku=Sku("A-17"), quantity=3)


_BUCHAREST = ZoneInfo("Europe/Bucharest")


@dataclass(frozen=True)
class Remind:
    """A plain ``datetime`` field, given a time the offset alone cannot place."""

    user_id: int
    at: datetime


class Channel(StrEnum):
    """A channel, handed to a field declared ``str``."""

    EMAIL = "email"
    SMS = "sms"


@dataclass(frozen=True)
class Notify:
    """A ``str`` field."""

    channel: str


@dataclass(frozen=True)
class Audit:
    """A dict of anything."""

    extra: dict[str, object]


@dataclass(frozen=True)
class Batch:
    """A ``list[int]`` field."""

    ids: list[int]


@dataclass(frozen=True)
class Charge:
    """A field declared ``object``."""

    amount: object


@dataclass(frozen=True)
class Callback:
    """A callable: nothing writes it."""

    call: Callable[[], int]


@dataclass(frozen=True)
class Guarded:
    """A lock in a field declared ``object``: nothing writes it."""

    lock: object


@dataclass(frozen=True)
class Signal:
    """A field whose type is imported for type checking only: nothing can build its writer."""

    event: Event


def refused_pairs() -> dict[str, tuple[object, object]]:
    """Return, by name, two messages of one class holding different data."""
    return {
        "repeated hour": (
            Remind(1, datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=_BUCHAREST)),
            Remind(2, datetime(2026, 10, 25, 3, 45, fold=1, tzinfo=_BUCHAREST)),
        ),
        "fold alone": (
            Remind(1, datetime(2026, 10, 25, 3, 30, tzinfo=_BUCHAREST)),
            Remind(1, datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=_BUCHAREST)),
        ),
        "naive": (Remind(1, datetime(2026, 1, 1, 9)), Remind(2, datetime(2026, 6, 1, 9))),
        "enum in str": (Notify(Channel.EMAIL), Notify(Channel.SMS)),
        "uuid in dict": (Audit({"by": UUID(int=1)}), Audit({"by": UUID(int=2)})),
        # The mismatch is the case.
        "tuple for list": (
            Batch((1, 2)),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            Batch((3, 4)),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        ),
        "decimal in object": (Charge(Decimal("1.50")), Charge(Decimal("2.50"))),
    }


def unwritable_pairs() -> dict[str, tuple[object, object]]:
    """Return, by name, two messages of one class holding values nothing can write."""
    return {
        "lambda": (Callback(lambda: 1), Callback(lambda: 2)),
        "lock": (Guarded(threading.Lock()), Guarded(threading.Lock())),
        "unresolved annotation": (Signal(threading.Event()), Signal(threading.Event())),
    }
