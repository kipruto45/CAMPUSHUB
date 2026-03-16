"""
Background Tasks for CampusHub.

This module provides:
- Base task classes
- Task utilities
- Task monitoring
"""

from apps.core.tasks.base import (
    # App
    app,
    # Base classes
    BaseTask,
    ScheduledTask,
    ResourceTask,
    UserTask,
    # Enums
    TaskPriority,
    TaskStatus,
    # Data classes
    TaskConfig,
    TaskResult,
    # Utilities
    schedule_task,
    schedule_periodic_task,
    run_task_group,
    run_task_chain,
    # Monitoring
    TaskMonitor,
)

__all__ = [
    "app",
    "BaseTask",
    "ScheduledTask",
    "ResourceTask",
    "UserTask",
    "TaskPriority",
    "TaskStatus",
    "TaskConfig",
    "TaskResult",
    "schedule_task",
    "schedule_periodic_task",
    "run_task_group",
    "run_task_chain",
    "TaskMonitor",
]
