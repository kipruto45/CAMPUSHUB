"""Signals for bookmark automations."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import UserActivity
from apps.activity.services import ActivityService
from apps.gamification.services import GamificationService

from .models import Bookmark
from .services import BookmarkService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Bookmark)
def bookmark_created(sender, instance, created, **kwargs):
    """Recalculate denormalized counters and log bookmark actions."""
    if created:
        BookmarkService.recalculate_user_bookmark_count(instance.user)
        try:
            GamificationService.sync_saved_resources_count(instance.user)
        except Exception:
            logger.exception(
                "Failed to sync gamification saved-resource count for bookmark_id=%s",
                instance.pk,
            )
        UserActivity.objects.create(
            user=instance.user,
            action="bookmark",
            description=f'Bookmarked resource "{instance.resource.title}"',
        )
        ActivityService.log_bookmark(instance.user, instance)


@receiver(post_delete, sender=Bookmark)
def bookmark_deleted(sender, instance, **kwargs):
    """Keep counters in sync after bookmark removal/cascade deletes."""
    BookmarkService.recalculate_user_bookmark_count(instance.user)
    try:
        GamificationService.sync_saved_resources_count(instance.user)
    except Exception:
        logger.exception(
            "Failed to sync gamification saved-resource count after bookmark delete for user_id=%s",
            instance.user_id,
        )
