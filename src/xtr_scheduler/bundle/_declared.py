"""What a kernel's scan found declared: schedule providers and tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.registry.declarations import task_name

if TYPE_CHECKING:
    from xtr_scheduler.recurring_message import RecurringMessage
    from xtr_scheduler.registry.task_declaration import TaskDeclaration

__all__ = ["Declared"]


@final
class Declared:
    """The schedule providers and tasks one kernel found, filled in while it builds."""

    __slots__ = ("functions", "providers", "schedules", "task_classes", "tasks")

    def __init__(self) -> None:
        """Start with nothing declared."""
        self.providers: dict[str, type[object]] = {}
        self.tasks: list[tuple[str, TaskDeclaration]] = []
        self.task_classes: dict[str, type[object]] = {}
        self.functions: dict[str, object] = {}
        self.schedules: dict[str, None] = {}

    def add_provider(self, name: str, provider: type[object]) -> None:
        """Record ``provider`` as the provider of the schedule ``name``.

        Raises:
            SchedulerLogicError: If another class already provides it.
        """
        claimed = self.providers.get(name)
        if claimed is not None and claimed is not provider:
            raise SchedulerLogicError(
                f'The schedule "{name}" is already provided by {task_name(claimed)}.'
            )
        self.providers[name] = provider

    def add_schedule(self, name: str) -> None:
        """Record that the schedule ``name`` exists, even with none of its tasks here.

        A schedule whose tasks all belong to other environments still exists in
        this one — empty — so its receiver does too, and a worker started for it
        runs rather than failing on an unknown transport.
        """
        self.schedules[name] = None

    def add_task(self, target: object, declaration: TaskDeclaration) -> None:
        """Record ``declaration``, calling ``target``."""
        self.add_schedule(declaration.schedule)
        name = task_name(target)
        if isinstance(target, type):
            self.task_classes[name] = target
        else:
            self.functions[name] = target
        self.tasks.append((name, declaration))

    def names(self) -> tuple[str, ...]:
        """Return every schedule name, providers first, in the order found."""
        found = dict.fromkeys(self.providers)
        found.update(self.schedules)
        return tuple(found)

    def recurring_messages(self, schedule: str) -> list[RecurringMessage]:
        """Build the recurring messages of the tasks declared on ``schedule``."""
        return [
            declaration.recurring_message(target)
            for target, declaration in self.tasks
            if declaration.schedule == schedule
        ]

    def task_methods(self) -> dict[str, frozenset[str]]:
        """Return the methods each task target may be called through, by target name.

        Built from this kernel's own declarations, so the handler refuses any
        method no decorator named here — the allow-list is the container's,
        never a process-wide registry's. A task declared with no ``method`` is
        called through ``__call__``.
        """
        methods: dict[str, set[str]] = {}
        for name, declaration in self.tasks:
            methods.setdefault(name, set()).add(declaration.method or "__call__")
        return {name: frozenset(allowed) for name, allowed in methods.items()}
