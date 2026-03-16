"""Signal handlers for rating automations."""

import logging

from django.db.models import Avg
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.activity.models import ActivityType, RecentActivity
from apps.gamification.services import GamificationService
from apps.notifications.services import NotificationService

from .models import Rating

logger = logging.getLogger(__name__)


def _recalculate_resource_rating(resource):
    aggregate = Rating.objects.filter(resource=resource).aggregate(avg=Avg("value"))
    resource.average_rating = round(float(aggregate["avg"] or 0), 2)
    resource.save(update_fields=["average_rating"])


@receiver(post_save, sender=Rating)
def rating_created_or_updated(sender, instance, created, **kwargs):
    """Automation hooks for rating create/update."""
    _recalculate_resource_rating(instance.resource)

    if created:
        if hasattr(instance.user, "profile"):
            profile = instance.user.profile
            profile.total_ratings = (profile.total_ratings or 0) + 1
            profile.save(update_fields=["total_ratings"])
        RecentActivity.objects.create(
            user=instance.user,
            resource=instance.resource,
            activity_type=ActivityType.RATED,
            metadata={"value": instance.value},
        )
        try:
            GamificationService.record_rating(instance.user, rating=instance)
        except Exception:
            logger.exception(
                "Failed to record gamification rating event for rating_id=%s",
                instance.pk,
            )
        if instance.resource.uploaded_by_id != instance.user_id:
            NotificationService.notify_new_rating(
                instance, instance.resource.uploaded_by
            )


@receiver(post_delete, sender=Rating)
def rating_deleted(sender, instance, **kwargs):
    """Keep aggregates in sync after rating removal."""
    _recalculate_resource_rating(instance.resource)
    if hasattr(instance.user, "profile"):
        profile = instance.user.profile
        total = Rating.objects.filter(user=instance.user).count()
        if profile.total_ratings != total:
            profile.total_ratings = total
            profile.save(update_fields=["total_ratings"])
