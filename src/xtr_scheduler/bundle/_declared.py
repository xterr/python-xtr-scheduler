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

    __slots__ = ("functions", "providers", "task_classes", "tasks")

    def __init__(self) -> None:
        """Start with nothing declared."""
        self.providers: dict[str, type[object]] = {}
        self.tasks: list[tuple[str, TaskDeclaration]] = []
        self.task_classes: dict[str, type[object]] = {}
        self.functions: dict[str, object] = {}

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

    def add_task(self, target: object, declaration: TaskDeclaration) -> None:
        """Record ``declaration``, calling ``target``."""
        name = task_name(target)
        if isinstance(target, type):
            self.task_classes[name] = target
        else:
            self.functions[name] = target
        self.tasks.append((name, declaration))

    def names(self) -> tuple[str, ...]:
        """Return every schedule name, providers first, in the order found."""
        found = dict.fromkeys(self.providers)
        found.update(dict.fromkeys(declaration.schedule for _name, declaration in self.tasks))
        return tuple(found)

    def recurring_messages(self, schedule: str) -> list[RecurringMessage]:
        """Build the recurring messages of the tasks declared on ``schedule``."""
        return [
            declaration.recurring_message(target)
            for target, declaration in self.tasks
            if declaration.schedule == schedule
        ]
