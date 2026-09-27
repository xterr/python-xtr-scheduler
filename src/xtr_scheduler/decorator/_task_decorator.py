"""What ``@as_cron_task`` and ``@as_periodic_task`` share: where a task is recorded."""

from __future__ import annotations

from types import FunctionType
from typing import TYPE_CHECKING, TypeVar, cast, final

from xtr_scheduler.registry.declarations import declare_task

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from xtr_scheduler.registry.task_declaration import TaskDeclaration

__all__ = ["declaring", "names"]

TargetT = TypeVar("TargetT")


@final
class _MethodTasks:
    """Stands in for a method until its class exists, then records its tasks on the class.

    A decorator in a class body sees a plain function; the class it belongs to
    does not exist yet. Python calls ``__set_name__`` once it does, and the
    tasks are recorded on the class, calling this method — then the function
    is put back where it was.
    """

    def __init__(self, function: Callable[..., object], declaration: TaskDeclaration) -> None:
        self.function = function
        self.declarations = [declaration]

    def __set_name__(self, owner: type, name: str) -> None:
        setattr(owner, name, self.function)
        for declaration in self.declarations:
            declare_task(owner, declaration.on_method(name))


def declaring(declaration: TaskDeclaration) -> Callable[[TargetT], TargetT]:
    """Return a decorator recording ``declaration`` on what it decorates."""

    def decorate(target: TargetT) -> TargetT:
        if isinstance(target, _MethodTasks):
            target.declarations.append(declaration)
            return target
        if isinstance(target, FunctionType) and _is_method(target):
            return cast("TargetT", _MethodTasks(target, declaration))
        declare_task(target, declaration)
        return target

    return decorate


def names(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Return ``value`` as a tuple of names: one string is one name."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _is_method(function: FunctionType) -> bool:
    """Tell whether ``function`` is being defined in a class body."""
    parts = function.__qualname__.split(".")
    return len(parts) > 1 and parts[-2] != "<locals>"
