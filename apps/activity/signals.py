"""
Signal handlers for activity app.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.gamification.services import GamificationService

from .models import RecentActivity

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Download)
def log_download_activity(sender, instance, created, **kwargs):
    """
    Log activity when a download occurs.
    """
    if created and instance.user:
        from .services import ActivityService
        from apps.resources.services import CourseProgressService

        ActivityService.log_download(
            user=instance.user,
            resource=instance.resource,
            personal_file=getattr(instance, "personal_file", None),
        )
        if instance.resource_id:
            CourseProgressService.sync_resource_completion(
                instance.user,
                instance.resource,
            )
        try:
            GamificationService.record_download(
                instance.user,
                resource=instance.resource,
                personal_file=getattr(instance, "personal_file", None),
            )
        except Exception:
            logger.exception(
                "Failed to record gamification download event for download_id=%s",
                instance.pk,
            )


@receiver(post_save, sender=Bookmark)
def log_bookmark_activity(sender, instance, created, **kwargs):
    """
    Log activity when a bookmark is created.
    """
    if created and instance.user:
        from .services import ActivityService

        ActivityService.log_bookmark(user=instance.user, bookmark=instance)


@receiver(post_save, sender=RecentActivity)
def stream_recent_activity(sender, instance, created, **kwargs):
    """Push newly created activities to admin activity WebSocket stream."""
    if not created:
        return

    from apps.notifications.websocket import WebSocketNotificationService

    WebSocketNotificationService.send_activity_update(
        activity_type=instance.activity_type,
        user=instance.user,
        resource=instance.resource,
        personal_file=instance.personal_file,
        metadata=instance.metadata,
    )
