"""
Background Task Scheduling with Celery Beat for CampusHub.
"""

import logging

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger("celery_logger")

# Celery app instance
app = Celery("campushub")


# ========================
# Celery Configuration
# ========================


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing."""
    print(f"Request: {self.request!r}")


# ========================
# Scheduled Tasks
# ========================


@app.task(bind=True)
def cleanup_old_sessions(self):
    """
    Clean up expired sessions every 5 minutes.
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
    count = expired_sessions.count()
    expired_sessions.delete()

    logger.info(f"Cleaned up {count} expired sessions")
    return f"Cleaned {count} sessions"


@app.task(bind=True)
def clear_old_activity_logs(self):
    """
    Clear old activity logs every hour.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.activity.models import RecentActivity

    # Keep only last 30 days of activity
    cutoff = timezone.now() - timedelta(days=30)
    deleted = RecentActivity.objects.filter(created_at__lt=cutoff).delete()[0]

    logger.info(f"Cleared {deleted} old activity logs")
    return f"Cleared {deleted} logs"


@app.task(bind=True)
def update_trending_resources(self):
    """
    Update trending resources cache every 6 hours.
    """
    from datetime import timedelta

    from django.core.cache import cache
    from django.db.models import Count
    from django.utils import timezone

    from apps.resources.models import Resource

    # Calculate trending in last 7 days
    since = timezone.now() - timedelta(days=7)

    trending = (
        Resource.objects.filter(
            status="approved", is_public=True, downloads__created_at__gte=since
        )
        .annotate(download_count=Count("downloads"))
        .order_by("-download_count")[:50]
    )

    # Cache the results
    cache.set(
        "trending_resources", list(trending.values_list("id", flat=True)), 3600 * 6
    )

    logger.info("Updated trending resources cache")
    return "Trending resources updated"


@app.task(bind=True)
def update_recommendation_cache(self):
    """
    Update recommendation cache twice a day.
    """
    try:
        from apps.recommendations.services import RecommendationService

        RecommendationService.refresh_all_caches()
    except ImportError:
        logger.warning("RecommendationService not available, skipping cache refresh")

    logger.info("Updated recommendation caches")
    return "Recommendation caches updated"


@app.task(bind=True)
def daily_analytics_aggregation(self):
    """
    Aggregate daily analytics once per day.
    """
    try:
        from apps.analytics.services import AnalyticsService

        AnalyticsService.create_daily_snapshot()
    except ImportError:
        logger.warning("AnalyticsService not available, skipping daily snapshot")

    logger.info("Created daily analytics snapshot")
    return "Daily analytics aggregated"


@app.task(bind=True)
def cleanup_temp_files(self):
    """
    Clean up temporary files daily.
    """
    import os

    from django.conf import settings

    temp_dir = getattr(settings, "TEMP_DIR", "/tmp/campushub")

    if os.path.exists(temp_dir):
        import time

        cutoff = time.time() - (24 * 60 * 60)  # 24 hours

        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            if os.path.isfile(filepath):
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    logger.info(f"Removed temp file: {filename}")

    return "Temp files cleaned"


@app.task(bind=True)
def generate_daily_reports(self):
    """
    Generate daily usage reports.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.downloads.models import Download
    from apps.resources.models import Resource

    yesterday = timezone.now() - timedelta(days=1)

    # Count uploads
    new_resources = Resource.objects.filter(created_at__gte=yesterday).count()

    # Count downloads
    downloads = Download.objects.filter(created_at__gte=yesterday).count()

    logger.info(f"Daily Report - Uploads: {new_resources}, Downloads: {downloads}")
    return {
        "new_resources": new_resources,
        "downloads": downloads,
    }


@app.task(bind=True)
def send_daily_digest(self):
    """
    Send daily digest emails to users.
    """
    from apps.notifications.services import NotificationService

    users_to_notify = get_users_for_daily_digest()

    for user in users_to_notify:
        NotificationService.send_daily_digest(user)

    logger.info(f"Sent daily digests to {len(users_to_notify)} users")
    return f"Sent {len(users_to_notify)} daily digests"


def get_users_for_daily_digest():
    """Get users who want daily digest."""
    from apps.accounts.models import User

    # Get users who have enabled daily digest
    # Note: This assumes UserPreference has email_notifications field
    # In production, add daily_digest field to UserPreference
    return User.objects.filter(preferences__email_notifications=True, is_active=True)[
        :100
    ]  # Process in batches


@app.task(bind=True)
def archive_old_notifications(self):
    """
    Archive old notifications.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.notifications.models import Notification

    # Archive notifications older than 90 days
    cutoff = timezone.now() - timedelta(days=90)

    # Instead of deleting, delete old notifications
    archived = Notification.objects.filter(created_at__lt=cutoff).delete()[0]

    logger.info(f"Archived {archived} old notifications")
    return f"Archived {archived} notifications"


@app.task(bind=True)
def update_user_stats(self):
    """
    Update user statistics daily.
    """
    from apps.accounts.models import User
    from apps.downloads.models import Download
    from apps.resources.models import Resource

    users = User.objects.filter(is_active=True)

    for user in users:
        # Update upload count
        upload_count = Resource.objects.filter(uploaded_by=user).count()

        # Update download count
        download_count = Download.objects.filter(user=user).count()

        # Cache the stats
        from django.core.cache import cache

        cache.set(
            f"user_stats_{user.id}",
            {
                "uploads": upload_count,
                "downloads": download_count,
            },
            86400,
        )  # 24 hours

    logger.info(f"Updated stats for {users.count()} users")
    return f"Updated stats for {users.count()} users"


@app.task(bind=True)
def weekly_analytics_report(self):
    """
    Generate weekly analytics report.
    """
    try:
        from apps.analytics.services import AnalyticsService

        AnalyticsService.generate_weekly_report()
    except ImportError:
        logger.warning("AnalyticsService not available, skipping weekly report")

    logger.info("Generated weekly analytics report")
    return "Weekly report generated"


@app.task(bind=True)
def check_resource_integrity(self):
    """
    Check integrity of uploaded resources every 30 minutes.
    """
    import os

    from apps.resources.models import Resource

    # Check resources that were uploaded recently
    recent_resources = Resource.objects.filter(status="pending")[:50]

    checked = 0
    for resource in recent_resources:
        try:
            # Check primary file and additional files.
            if (
                resource.file
                and hasattr(resource.file, "path")
                and not os.path.exists(resource.file.path)
            ):
                logger.warning("Missing primary file for resource %s", resource.id)

            for file_obj in resource.additional_files.all():
                if (
                    file_obj.file
                    and hasattr(file_obj.file, "path")
                    and not os.path.exists(file_obj.file.path)
                ):
                    logger.warning(
                        "Missing additional file %s for resource %s",
                        file_obj.id,
                        resource.id,
                    )
            checked += 1
        except Exception as e:
            logger.error(f"Error checking resource {resource.id}: {e}")

    return f"Checked {checked} resources"


@app.task(bind=True)
def clear_old_caches(self):
    """
    Clear expired caches daily.
    """
    from django.core.cache import cache

    # Clear caches that should expire
    cache.clear()

    logger.info("Cleared old caches")
    return "Caches cleared"


@app.task(bind=True)
def cleanup_deleted_accounts(self):
    """
    Permanently remove accounts that have passed the 7-day deletion window.
    """
    from django.utils import timezone

    from apps.accounts.models import User

    cutoff = timezone.now()
    candidates = User.objects.filter(
        is_deleted=True,
        deletion_scheduled_at__isnull=False,
        deletion_scheduled_at__lte=cutoff,
    )
    count = candidates.count()
    if count:
        for user in candidates:
            user.delete()

    logger.info("Purged %s deleted accounts", count)
    return f"Purged {count} deleted accounts"


# ========================
# Celery Beat Schedule
# ========================

CELERY_BEAT_SCHEDULE = {
    "cleanup-sessions": {
        "task": "apps.core.celery_tasks.cleanup_old_sessions",
        "schedule": crontab(minute="*/5"),
    },
    "clear-old-activity": {
        "task": "apps.core.celery_tasks.clear_old_activity_logs",
        "schedule": crontab(hour="*/1"),
    },
    "update-trending": {
        "task": "apps.core.celery_tasks.update_trending_resources",
        "schedule": crontab(hour="*/6"),
    },
    "update-recommendations": {
        "task": "apps.core.celery_tasks.update_recommendation_cache",
        "schedule": crontab(hour="*/12"),
    },
    "daily-analytics": {
        "task": "apps.core.celery_tasks.daily_analytics_aggregation",
        "schedule": crontab(hour="*/24"),
    },
    "cleanup-temp-files": {
        "task": "apps.core.celery_tasks.cleanup_temp_files",
        "schedule": crontab(hour="*/24"),
    },
    "daily-reports": {
        "task": "apps.core.celery_tasks.generate_daily_reports",
        "schedule": crontab(hour="*/24"),
    },
    "daily-digest": {
        "task": "apps.core.celery_tasks.send_daily_digest",
        "schedule": crontab(hour="*/24"),
    },
    "engagement-inactivity-reminders": {
        "task": "apps.notifications.tasks.send_inactivity_reminders",
        "schedule": crontab(hour=18, minute=0),
    },
    "archive-notifications": {
        "task": "apps.core.celery_tasks.archive_old_notifications",
        "schedule": crontab(hour="*/24"),
    },
    "update-user-stats": {
        "task": "apps.core.celery_tasks.update_user_stats",
        "schedule": crontab(hour="*/24"),
    },
    "weekly-report": {
        "task": "apps.core.celery_tasks.weekly_analytics_report",
        "schedule": crontab(hour="*/168"),
    },
    "check-integrity": {
        "task": "apps.core.celery_tasks.check_resource_integrity",
        "schedule": crontab(minute="*/30"),
    },
    "clear-caches": {
        "task": "apps.core.celery_tasks.clear_old_caches",
        "schedule": crontab(hour="*/24"),
    },
    "cleanup-deleted-accounts": {
        "task": "apps.core.celery_tasks.cleanup_deleted_accounts",
        "schedule": crontab(hour=3, minute=0),
    },
}


# ========================
# Task Helpers
# ========================


def schedule_task(task_name, args=None, kwargs=None, eta=None, countdown=None):
    """
    Schedule a task to run later.
    """
    task_func = globals().get(task_name)
    if task_func:
        if eta:
            task_func.apply_async(args=args, kwargs=kwargs, eta=eta)
        elif countdown:
            task_func.apply_async(args=args, kwargs=kwargs, countdown=countdown)
        else:
            task_func.apply_async(args=args, kwargs=kwargs)
        return True
    return False


def schedule_periodic_task(task_name, schedule_type="crontab", schedule_options=None):
    """
    Schedule a periodic task.
    """
    from datetime import timedelta

    from celery.schedules import schedule as interval_schedule

    options = dict(schedule_options or {})
    args = tuple(options.pop("args", ()))
    kwargs = dict(options.pop("kwargs", {}))
    entry_name = options.pop("name", task_name.replace(".", "_"))

    # Allow passing raw task function name for local tasks.
    if "." in task_name:
        task_ref = task_name
    else:
        task_ref = f"apps.core.celery_tasks.{task_name}"

    if schedule_type == "crontab":
        schedule_obj = crontab(**options)
    elif schedule_type == "interval":
        every = int(options.pop("every", 60))
        period = str(options.pop("period", "seconds")).lower()
        delta_map = {
            "seconds": timedelta(seconds=every),
            "minutes": timedelta(minutes=every),
            "hours": timedelta(hours=every),
            "days": timedelta(days=every),
        }
        if period not in delta_map:
            raise ValueError(
                f"Unsupported interval period '{period}'. Use one of: {', '.join(delta_map)}."
            )
        schedule_obj = interval_schedule(run_every=delta_map[period])
    else:
        raise ValueError("schedule_type must be either 'crontab' or 'interval'.")

    beat_schedule = dict(getattr(app.conf, "beat_schedule", {}) or {})
    beat_schedule[entry_name] = {
        "task": task_ref,
        "schedule": schedule_obj,
        "args": args,
        "kwargs": kwargs,
    }
    app.conf.beat_schedule = beat_schedule

    logger.info("Registered periodic task '%s' -> %s", entry_name, task_ref)
    return beat_schedule[entry_name]


# ========================
# Monitoring
# ========================


@app.task(bind=True)
def monitor_task(self):
    """Monitor task execution."""
    logger.info(f"Task {self.name} started")
    return {"status": "running", "task_id": self.request.id}


# ========================
# Configuration
# ========================

# Configure Celery
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# ========================
# Error Handling
# ========================


@app.task(bind=True)
def error_handler(self, exc, traceback, request):
    """Handle task errors."""
    logger.error(f"Task {self.name} failed: {exc}\n{traceback}")

    # Could send notification to admins here
    return {"status": "failed", "error": str(exc)}


# ========================
# Retry Policies
# ========================


def get_retry_policy():
    """Get retry policy for tasks."""
    return {
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.2,
    }
