"""
Enhanced Background Jobs System for CampusHub.

Provides:
- Task base classes
- Task scheduling utilities
- Task monitoring
- Error handling
"""

import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

from celery import Celery, Task, group, chain, chord
from celery.schedules import crontab
from django.utils import timezone

logger = logging.getLogger("celery")


app = Celery("campushub")


class TaskPriority(Enum):
    """Task priority levels."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


@dataclass
class TaskResult:
    """Task execution result."""
    status: TaskStatus
    result: Any = None
    error: str = None
    traceback: str = None
    started_at: datetime = None
    completed_at: datetime = None
    duration: float = None
    
    @classmethod
    def success(cls, result: Any = None) -> 'TaskResult':
        now = timezone.now()
        return cls(
            status=TaskStatus.SUCCESS,
            result=result,
            started_at=now,
            completed_at=now,
            duration=0.0,
        )
    
    @classmethod
    def failure(cls, error: str, traceback: str = None) -> 'TaskResult':
        now = timezone.now()
        return cls(
            status=TaskStatus.FAILURE,
            error=error,
            traceback=traceback,
            started_at=now,
            completed_at=now,
            duration=0.0,
        )


@dataclass
class TaskConfig:
    """Task configuration."""
    name: str = None
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: int = 300  # seconds
    rate_limit: str = None  # e.g., "100/m"
    autoretry_for: tuple = (Exception,)
    retry_backoff: bool = True
    retry_backoff_max: int = 600


class BaseTask(Task):
    """
    Base class for all CampusHub tasks.
    
    Features:
    - Automatic logging
    - Error handling
    - Result caching
    - Monitoring
    """
    
    # Configuration
    abstract = True
    max_retries = 3
    default_retry_delay = 60
    
    # Track task execution
    _task_id: str = None
    _started_at: datetime = None
    
    def __call__(self, *args, **kwargs):
        self._task_id = self.request.id
        self._started_at = timezone.now()
        
        logger.info(f"Task {self.name} [{self._task_id}] started")
        
        return super().__call__(*args, **kwargs)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            f"Task {self.name} [{task_id}] failed: {exc}\n{traceback.format_exc()}"
        )
        
        # Cache failure result
        try:
            from apps.core.cache.enhanced import CacheService
            result_key = f"task_result:{task_id}"
            CacheService.set(
                result_key,
                {
                    "status": "failure",
                    "error": str(exc),
                    "traceback": str(einfo),
                    "completed_at": timezone.now().isoformat(),
                },
                timeout=3600,
            )
        except Exception:
            pass
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        duration = (timezone.now() - self._started_at).total_seconds()
        logger.info(f"Task {self.name} [{task_id}] succeeded in {duration:.2f}s")
        
        # Cache success result
        try:
            from apps.core.cache.enhanced import CacheService
            result_key = f"task_result:{task_id}"
            CacheService.set(
                result_key,
                {
                    "status": "success",
                    "result": str(retval),
                    "duration": duration,
                    "completed_at": timezone.now().isoformat(),
                },
                timeout=3600,
            )
        except Exception:
            pass
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(
            f"Task {self.name} [{task_id}] retrying: {exc}"
        )


class ScheduledTask(BaseTask):
    """Base class for scheduled tasks."""
    
    abstract = True
    
    # Schedule configuration (override in subclass)
    schedule = None  # crontab or timedelta
    run_every = None  # Alternative: timedelta
    
    @abstractmethod
    def run(self, *args, **kwargs):
        """Execute the task."""
        pass


class ResourceTask(BaseTask):
    """Base class for resource-related tasks."""
    
    abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle resource task failure."""
        resource_id = args[0] if args else kwargs.get('resource_id')
        logger.error(f"Resource task failed for resource {resource_id}: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


class UserTask(BaseTask):
    """Base class for user-related tasks."""
    
    abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle user task failure."""
        user_id = args[0] if args else kwargs.get('user_id')
        logger.error(f"User task failed for user {user_id}: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


# Task utilities
def schedule_task(
    task_func: Callable,
    args: tuple = None,
    kwargs: dict = None,
    countdown: int = None,
    eta: datetime = None,
    priority: TaskPriority = TaskPriority.NORMAL,
) -> Any:
    """
    Schedule a task to run.
    
    Usage:
        # Run in 5 minutes
        schedule_task(some_task, args=(1, 2), countdown=300)
        
        # Run at specific time
        schedule_task(some_task, args=(1,), eta=datetime.now() + timedelta(hours=1))
    """
    options = {}
    if countdown:
        options['countdown'] = countdown
    if eta:
        options['eta'] = eta
    
    return task_func.apply_async(args=args or (), kwargs=kwargs or {}, **options)


def schedule_periodic_task(
    task_func: Callable,
    schedule,
    args: tuple = None,
    kwargs: dict = None,
    name: str = None,
) -> dict:
    """
    Schedule a periodic task.
    
    Usage:
        # Every hour
        schedule_periodic_task(
            cleanup_task,
            schedule=crontab(minute=0),
            name="hourly-cleanup"
        )
        
        # Every day at midnight
        schedule_periodic_task(
            daily_report_task,
            schedule=crontab(hour=0, minute=0),
            name="daily-report"
        )
    """
    from celery.schedules import schedule as celery_schedule
    
    if isinstance(schedule, timedelta):
        schedule = celery_schedule(run_every=schedule)
    elif isinstance(schedule, dict):
        schedule = crontab(**schedule)
    
    beat_schedule = dict(app.conf.beat_schedule or {})
    entry_name = name or task_func.__name__
    
    beat_schedule[entry_name] = {
        "task": f"{task_func.__module__}.{task_func.__name__}",
        "schedule": schedule,
        "args": args or (),
        "kwargs": kwargs or {},
    }
    
    app.conf.beat_schedule = beat_schedule
    return beat_schedule[entry_name]


def run_task_group(tasks: list[tuple], options: dict = None) -> group:
    """
    Run multiple tasks in parallel.
    
    Usage:
        result = run_task_group([
            (task1, (1, 2), {}),
            (task2, (), {"value": 10}),
        ])
    """
    jobs = []
    for task, args, kwargs in tasks:
        jobs.append(task.s(*args, **kwargs))
    
    return group(jobs)


def run_task_chain(tasks: list[tuple], options: dict = None) -> chain:
    """
    Run multiple tasks in sequence.
    
    Usage:
        result = run_task_chain([
            (task1, (1,), {}),
            (task2, (), {}),
        ])
    """
    jobs = []
    for task, args, kwargs in tasks:
        jobs.append(task.s(*args, **kwargs))
    
    return chain(*jobs)


# Task monitoring
class TaskMonitor:
    """Monitor task execution."""
    
    @staticmethod
    def get_task_status(task_id: str) -> dict:
        """Get task status."""
        try:
            from apps.core.cache.enhanced import CacheService
            result = CacheService.get(f"task_result:{task_id}")
            if result:
                return result
            
            # Try to get from Celery result backend
            from celery.result import AsyncResult
            result = AsyncResult(task_id)
            return {
                "status": result.state,
                "result": result.result if result.ready() else None,
            }
        except Exception as e:
            return {"status": "unknown", "error": str(e)}
    
    @staticmethod
    def get_active_tasks() -> list:
        """Get active tasks."""
        try:
            inspect = app.control.inspect()
            active = inspect.active()
            return active if active else {}
        except Exception:
            return {}
    
    @staticmethod
    def get_scheduled_tasks() -> list:
        """Get scheduled tasks."""
        try:
            inspect = app.control.inspect()
            scheduled = inspect.scheduled()
            return scheduled if scheduled else {}
        except Exception:
            return {}
    
    @staticmethod
    def get_worker_stats() -> dict:
        """Get worker statistics."""
        try:
            inspect = app.control.inspect()
            stats = inspect.stats()
            return stats if stats else {}
        except Exception:
            return {}


# Configure Celery
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Default task configurations
DEFAULT_TASK_CONFIG = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "Africa/Nairobi",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 300,
    "task_soft_time_limit": 240,
    "worker_prefetch_multiplier": 4,
    "worker_max_tasks_per_child": 1000,
}
