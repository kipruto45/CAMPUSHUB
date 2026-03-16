"""
Celery configuration for CampusHub project.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("campus_hub")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")


# Celery Beat Schedule
app.conf.beat_schedule = {
    "cleanup-old-downloads": {
        "task": "apps.downloads.tasks.cleanup_old_downloads",
        "schedule": 86400.0,  # Run daily
    },
    "update-trending-resources": {
        "task": "apps.resources.tasks.update_trending_resources",
        "schedule": 3600.0,  # Run hourly
    },
    "send-daily-notifications": {
        "task": "apps.notifications.tasks.send_daily_notifications",
        "schedule": 86400.0,  # Run daily
    },
}
