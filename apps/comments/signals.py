"""Signal handlers for comment automations."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.activity.models import ActivityType, RecentActivity
from apps.gamification.services import GamificationService
from apps.notifications.services import NotificationService

from .models import Comment

logger = logging.getLogger(__name__)


def _recalculate_user_comment_count(user):
    if hasattr(user, "profile"):
        total = Comment.objects.filter(user=user, is_deleted=False).count()
        if user.profile.total_comments != total:
            user.profile.total_comments = total
            user.profile.save(update_fields=["total_comments"])


@receiver(post_save, sender=Comment)
def comment_created_or_updated(sender, instance, created, **kwargs):
    """Automate notifications, counts, and activity on comment changes."""
    _recalculate_user_comment_count(instance.user)

    if not created:
        return

    RecentActivity.objects.create(
        user=instance.user,
        resource=instance.resource,
        activity_type=ActivityType.COMMENTED,
        metadata={"comment_id": str(instance.id)},
    )
    try:
        GamificationService.record_comment(instance.user, comment=instance)
    except Exception:
        logger.exception(
            "Failed to record gamification comment event for comment_id=%s",
            instance.pk,
        )

    # Notify uploader about new comment.
    if instance.resource.uploaded_by_id != instance.user_id:
        NotificationService.notify_new_comment(instance, instance.resource.uploaded_by)

    # Notify parent commenter about reply.
    if instance.parent_id and instance.parent.user_id != instance.user_id:
        NotificationService.notify_comment_reply(instance, instance.parent.user)


@receiver(post_delete, sender=Comment)
def comment_deleted(sender, instance, **kwargs):
    """Keep user comment totals synchronized after deletion/cascade."""
    _recalculate_user_comment_count(instance.user)
