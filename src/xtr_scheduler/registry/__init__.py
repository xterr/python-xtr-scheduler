"""What the application declared with the scheduler's decorators."""

from __future__ import annotations

from .declarations import schedules_declared_on, task_name, tasks_declared_on
from .declared_schedules import (
    declared_schedules,
    declared_task_methods,
    declared_task_targets,
    schedule_of,
)
from .schedule_with_tasks import ScheduleWithTasks
from .task_declaration import TaskDeclaration

__all__ = [
    "ScheduleWithTasks",
    "TaskDeclaration",
    "declared_schedules",
    "declared_task_methods",
    "declared_task_targets",
    "schedule_of",
    "schedules_declared_on",
    "task_name",
    "tasks_declared_on",
]
