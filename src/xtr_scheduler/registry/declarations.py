"""What the scheduler's decorators recorded, on each object and for the process.

The decorators write twice. On the decorated object, so a container's scan
finds the declarations where it finds everything else, and reads them with
:func:`schedules_declared_on` and :func:`tasks_declared_on`. And in this
process, so an application with no container — whose transport discovery
builds the scheduler's transport factory with no arguments — still finds
them.
"""

from __future__ import annotations

from types import FunctionType
from typing import Final, cast

from xtr_scheduler.exception import SchedulerLogicError

from .task_declaration import TaskDeclaration

__all__ = [
    "SCHEDULES_ATTRIBUTE",
    "TASKS_ATTRIBUTE",
    "declare_schedule",
    "declare_task",
    "declared_schedule_class",
    "declared_schedule_names",
    "declared_tasks",
    "reset_declarations",
    "schedules_declared_on",
    "task_name",
    "tasks_declared_on",
]

SCHEDULES_ATTRIBUTE: Final = "__xtr_scheduler_schedules__"
TASKS_ATTRIBUTE: Final = "__xtr_scheduler_tasks__"

_SCHEDULES: dict[str, list[type]] = {}
_TASKS: list[tuple[object, TaskDeclaration]] = []


def task_name(target: object) -> str:
    """Return the name a task target is known under: its module and qualified name."""
    kind = target if isinstance(target, (type, FunctionType)) else type(target)
    return f"{kind.__module__}.{kind.__qualname__}"


def declare_schedule(provider: type, name: str) -> None:
    """Record ``provider`` as a provider of the schedule ``name``.

    Two classes may claim one name in a process — two applications, or two
    test suites — as long as they never run together: a kernel refuses the
    pair when its scan finds both, and :func:`declared_schedule_class` when
    it is asked for that schedule.
    """
    claimants = _SCHEDULES.setdefault(name, [])
    if provider not in claimants:
        claimants.append(provider)
    _append(provider, SCHEDULES_ATTRIBUTE, name)


def declare_task(target: object, declaration: TaskDeclaration) -> None:
    """Record ``declaration`` as a task calling ``target``.

    Raises:
        SchedulerLogicError: If the task names a private method. A call
            crossing a transport from another worker may reach only a method a
            decorator declared, never a private or dunder name — so a task
            declared on one is refused where it is written, not accepted here
            and refused on every run.
    """
    method = declaration.method
    if method is not None and method != "__call__" and method.startswith("_"):
        raise SchedulerLogicError(
            f'The task "{task_name(target)}" declares the private method "{method}".'
        )
    _TASKS.append((target, declaration))
    _append(target, TASKS_ATTRIBUTE, declaration)


def schedules_declared_on(obj: object) -> tuple[str, ...]:
    """Return the names of the schedules ``@as_schedule`` declared ``obj`` the provider of."""
    return tuple(name for name in _own(obj, SCHEDULES_ATTRIBUTE) if isinstance(name, str))


def tasks_declared_on(obj: object) -> tuple[TaskDeclaration, ...]:
    """Return the tasks declared on ``obj``, in the order they were declared."""
    recorded = _own(obj, TASKS_ATTRIBUTE)
    return tuple(task for task in recorded if isinstance(task, TaskDeclaration))


def declared_schedule_names() -> tuple[str, ...]:
    """Return every schedule declared in this process — by a provider or by a task."""
    found = dict.fromkeys(_SCHEDULES)
    found.update(dict.fromkeys(declaration.schedule for _target, declaration in _TASKS))
    return tuple(found)


def declared_schedule_class(name: str) -> type | None:
    """Return the class declared as the provider of the schedule ``name``, if any.

    Raises:
        SchedulerLogicError: If two classes provide it.
    """
    claimants = _SCHEDULES.get(name, [])
    if len(claimants) > 1:
        listed = ", ".join(task_name(claimant) for claimant in claimants)
        raise SchedulerLogicError(f'The schedule "{name}" is provided by {listed}.')
    return claimants[0] if claimants else None


def declared_tasks() -> tuple[tuple[object, TaskDeclaration], ...]:
    """Return every task declared in this process, with its target, in declaration order."""
    return tuple(_TASKS)


def _own(obj: object, attribute: str) -> tuple[object, ...]:
    """Return what was recorded on ``obj`` itself — never what a base class carries."""
    recorded: object = vars(obj).get(attribute, ()) if hasattr(obj, "__dict__") else ()
    return cast("tuple[object, ...]", recorded) if isinstance(recorded, tuple) else ()


def _append(obj: object, attribute: str, value: object) -> None:
    setattr(obj, attribute, (*_own(obj, attribute), value))


def reset_declarations() -> None:
    """Forget every schedule and task declared in this process.

    What the process-wide declarations hold is kept for good — a module is
    imported once — so a test declaring its own calls this to start from
    nothing, and to leave nothing for the next. The marks on the classes and
    functions themselves stay: a kernel's scan still finds them.
    """
    _SCHEDULES.clear()
    _TASKS.clear()
