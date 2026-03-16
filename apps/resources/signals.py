"""Signal handlers for resource automations."""

import logging

from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.activity.models import ActivityType, RecentActivity
from apps.downloads.models import Download
from apps.gamification.services import GamificationService

from .models import Resource
from .services import ResourceUploadService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Resource)
def resource_created_or_updated(sender, instance, created, **kwargs):
    """
    Keep denormalized user counters synchronized.

    Automations:
    - upload count refresh
    - storage usage refresh
    - uploader activity feed refresh
    - send upload confirmation notification
    """
    if not instance.uploaded_by_id:
        return

    ResourceUploadService.recalculate_user_upload_counts(instance.uploaded_by)
    ResourceUploadService.recalculate_user_storage_usage(instance.uploaded_by)

    if created:
        try:
            GamificationService.record_upload(instance.uploaded_by, resource=instance)
        except Exception:
            logger.exception(
                "Failed to record gamification upload event for resource_id=%s",
                instance.pk,
            )
        RecentActivity.objects.create(
            user=instance.uploaded_by,
            activity_type=ActivityType.CREATED_RESOURCE,
            resource=instance,
        )
        
        # Send upload confirmation notification to uploader
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                recipient=instance.uploaded_by,
                title="Resource Uploaded Successfully",
                message=f'Your resource "{instance.title}" is now live automatically.',
                notification_type="system",
            )
        except Exception:
            logger.exception(
                "Failed to send upload confirmation notification for resource_id=%s",
                instance.pk,
            )


@receiver(post_delete, sender=Resource)
def resource_deleted(sender, instance, **kwargs):
    """Refresh denormalized counters after resource deletion."""
    if not instance.uploaded_by_id:
        return
    ResourceUploadService.recalculate_user_upload_counts(instance.uploaded_by)
    ResourceUploadService.recalculate_user_storage_usage(instance.uploaded_by)


def track_resource_view(resource: Resource, user=None):
    """Automation hook for resource detail views."""
    Resource.objects.filter(pk=resource.pk).update(view_count=F("view_count") + 1)
    if user and user.is_authenticated:
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )


def track_resource_download(resource: Resource, user=None, request=None):
    """Automation hook for resource downloads."""
    Resource.objects.filter(pk=resource.pk).update(
        download_count=F("download_count") + 1
    )
    if user and user.is_authenticated:
        download_kwargs = {"user": user, "resource": resource}
        if request:
            from apps.core.utils import get_client_ip, get_user_agent

            download_kwargs["ip_address"] = get_client_ip(request)
            download_kwargs["user_agent"] = get_user_agent(request)
        Download.objects.create(**download_kwargs)
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.DOWNLOADED_RESOURCE,
        )


def track_resource_share(resource: Resource, user=None):
    """
    Automation hook for resource shares.
    Share count and share-event analytics are handled by ResourceShareService.
    """
    from apps.activity.models import ActivityType, RecentActivity

    if user and user.is_authenticated:
        # Record in activity feed
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.SHARED_RESOURCE,
        )

        try:
            GamificationService.record_share(user, resource=resource)
        except Exception:
            # Gamification failure should not break sharing
            pass


def track_resource_approval(resource, reviewer, reason):
    """Create version when resource is approved."""
    from .models import ResourceVersion
    ResourceVersion.create_version(
        resource=resource,
        action="approved",
        changed_by=reviewer,
        change_summary=reason or "Resource approved",
    )


def track_resource_rejection(resource, reviewer, reason):
    """Create version when resource is rejected."""
    from .models import ResourceVersion
    ResourceVersion.create_version(
        resource=resource,
        action="rejected",
        changed_by=reviewer,
        change_summary=reason or "Resource rejected",
    )


def track_resource_archive(resource):
    """Create version when resource is archived."""
    from .models import ResourceVersion
    ResourceVersion.create_version(
        resource=resource,
        action="archived",
        change_summary="Resource archived",
    )
