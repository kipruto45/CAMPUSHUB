"""
Celery tasks for resource automations.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def process_new_resource(resource_id):
    """
    Process newly uploaded resource:
    - Auto-tag
    - Index for search
    """
    from .automations import suggest_tags
    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id, is_deleted=False)

        # Auto-generate tags if none provided
        if not resource.tags:
            tags = suggest_tags(
                resource.title, resource.description, resource.resource_type
            )
            resource.tags = ",".join(tags)
            resource.save(update_fields=["tags"])

        logger.info(f"Processed new resource {resource_id}")
    except Exception as e:
        logger.error(f"Error processing resource {resource_id}: {e}")


@shared_task
def update_trending_resources():
    """
    Update trending resources cache.
    Runs hourly.
    """
    from .automations import calculate_trending_score
    from .models import Resource

    try:
        resources = Resource.objects.filter(status="approved", is_public=True, is_deleted=False)

        trending_data = {}
        for resource in resources:
            score = calculate_trending_score(resource)
            trending_data[str(resource.id)] = score

        # Store in cache for quick access
        from django.core.cache import cache

        cache.set("trending_resources", trending_data, 3600)  # 1 hour

        logger.info(f"Updated trending scores for {len(trending_data)} resources")
    except Exception as e:
        logger.error(f"Error updating trending resources: {e}")


@shared_task
def cleanup_old_downloads():
    """
    Clean up old download history.
    Runs daily.
    """
    from apps.downloads.models import Download

    try:
        # Keep last 90 days of downloads
        cutoff = timezone.now() - timedelta(days=90)
        deleted_count = Download.objects.filter(created_at__lt=cutoff).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old download records")
    except Exception as e:
        logger.error(f"Error cleaning up downloads: {e}")


@shared_task
def send_upload_confirmation(resource_id):
    """
    Send upload confirmation email.
    """
    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id, is_deleted=False)

        from apps.core.emails import EmailService

        EmailService.send_email(
            subject=f"Resource Uploaded: {resource.title}",
            message=f'Your resource "{resource.title}" is now live automatically.',
            recipient_list=[resource.uploaded_by.email],
            fail_silently=False,
        )

        logger.info(f"Sent upload confirmation for resource {resource_id}")
    except Exception as e:
        logger.error(f"Error sending upload confirmation: {e}")


@shared_task
def notify_resource_approved(resource_id):
    """
    Notify user when resource is approved.
    """
    from apps.notifications.models import Notification

    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id, is_deleted=False)

        Notification.objects.create(
            recipient=resource.uploaded_by,
            title="Resource Approved",
            message=f'Your resource "{resource.title}" has been approved and is now visible to all students.',
            notification_type="resource_approved",
        )

        logger.info(f"Sent approval notification for resource {resource_id}")
    except Exception as e:
        logger.error(f"Error sending approval notification: {e}")


@shared_task
def notify_resource_rejected(resource_id, reason=""):
    """
    Notify user when resource is rejected.
    """
    from apps.notifications.models import Notification

    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id, is_deleted=False)

        message = f'Your resource "{resource.title}" has been rejected.'
        if reason:
            message += f" Reason: {reason}"

        Notification.objects.create(
            recipient=resource.uploaded_by,
            title="Resource Rejected",
            message=message,
            notification_type="resource_rejected",
        )

        logger.info(f"Sent rejection notification for resource {resource_id}")
    except Exception as e:
        logger.error(f"Error sending rejection notification: {e}")


@shared_task
def notify_new_comment(resource_id, comment_id):
    """
    Notify resource owner of new comment.
    """
    from apps.comments.models import Comment
    from apps.notifications.models import Notification

    from .models import Resource

    try:
        comment = Comment.objects.get(id=comment_id)
        resource = Resource.objects.get(id=resource_id, is_deleted=False)

        # Don't notify if user commented on their own resource
        if comment.user != resource.uploaded_by:
            Notification.objects.create(
                recipient=resource.uploaded_by,
                title="New Comment",
                message=f'{comment.user.full_name} commented on "{resource.title}"',
                notification_type="new_comment",
            )

        logger.info(f"Sent comment notification for resource {resource_id}")
    except Exception as e:
        logger.error(f"Error sending comment notification: {e}")


@shared_task
def calculate_storage_usage():
    """
    Calculate and update storage usage for all users.
    Runs daily.
    """
    from django.contrib.auth import get_user_model

    from .models import UserStorage

    User = get_user_model()

    try:
        users = User.objects.filter(is_active=True)

        for user in users:
            storage, _ = UserStorage.objects.get_or_create(user=user)

            # Calculate from personal resources
            from .models import PersonalResource

            personal_size = (
                PersonalResource.objects.filter(user=user).aggregate(
                    total=Sum("file_size")
                )["total"]
                or 0
            )

            # Calculate from public uploads
            from .models import Resource

            public_size = (
                Resource.objects.filter(uploaded_by=user).aggregate(
                    total=Sum("file_size")
                )["total"]
                or 0
            )

            storage.used_storage = personal_size + public_size
            storage.save(update_fields=["used_storage"])

        logger.info(f"Updated storage usage for {users.count()} users")
    except Exception as e:
        logger.error(f"Error calculating storage: {e}")


@shared_task
def send_weekly_digest():
    """
    Send weekly digest of trending resources.
    Runs weekly.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.models import Notification

    from .automations import get_trending_resources

    User = get_user_model()

    try:
        trending = get_trending_resources(limit=5)

        if not trending:
            return

        # Get active users
        users = User.objects.filter(is_active=True, role="student")

        for user in users:
            trending_titles = ", ".join([r.title for r in trending[:3]])

            Notification.objects.create(
                recipient=user,
                title="Weekly Trending Resources",
                message=f"Check out this week's trending: {trending_titles}",
                notification_type="trending",
            )

        logger.info(f"Sent weekly digest to {users.count()} users")
    except Exception as e:
        logger.error(f"Error sending weekly digest: {e}")


@shared_task
def check_storage_warnings():
    """
    Check for users approaching storage limits.
    Runs daily.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.models import Notification

    from .models import UserStorage

    get_user_model()

    try:
        storages = UserStorage.objects.filter(used_storage__gt=0)

        for storage in storages:
            percentage = storage.get_usage_percentage()

            if percentage >= 90:
                Notification.objects.create(
                    recipient=storage.user,
                    title="Storage Almost Full",
                    message=f"Your storage is {percentage:.1f}% full. Please delete some files.",
                    notification_type="storage_warning",
                )

        logger.info(f"Checked storage warnings for {storages.count()} users")
    except Exception as e:
        logger.error(f"Error checking storage warnings: {e}")


@shared_task
def detect_duplicate_resources():
    """
    Detect potential duplicate resources.
    Runs weekly.
    """

    from .models import Resource

    try:
        # Find resources with similar titles
        resources = Resource.objects.filter(status="approved")

        for resource in resources:
            # Check for similar titles
            similar = Resource.objects.filter(
                status="approved", title__icontains=resource.title[:20]
            ).exclude(id=resource.id)

            if similar.exists():
                # Could flag for review or auto-notify
                logger.info(
                    f"Found {similar.count()} potential duplicates for {resource.title}"
                )

        logger.info("Completed duplicate detection")
    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}")
