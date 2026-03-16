"""
Celery tasks for downloads app.
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cleanup_old_downloads():
    """Clean up old download records."""
    # Keep downloads for 90 days
    threshold = timezone.now() - timedelta(days=90)
    from .models import Download

    deleted_count = Download.objects.filter(created_at__lt=threshold).delete()[0]
    return f"Cleaned up {deleted_count} old download records"
