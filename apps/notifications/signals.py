"""
Notification signals for automatic push notifications.
Triggers FCM notifications on various events.
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.announcements.models import Announcement
from apps.comments.models import Comment
from apps.notifications.fcm import (NotificationPriority, PushNotification,
                                    fcm_service)
from apps.resources.models import Resource

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Resource)
def resource_status_changed(sender, instance, created, **kwargs):
    """
    Send push notification when a resource is approved or rejected.
    """
    update_fields = kwargs.get("update_fields")
    if not created and instance.status in ["approved", "rejected"] and (
        update_fields is None or "status" in update_fields
    ):
        user = instance.uploaded_by
        if not user:
            return

        if instance.status == "approved":
            title = "✅ Resource Approved!"
            body = f'Your resource "{instance.title}" has been approved and is now available.'
        else:
            title = "❌ Resource Rejected"
            body = f'Your resource "{instance.title}" was not approved. Please check the feedback.'

        # Get user's active device tokens
        tokens = list(
            user.device_tokens.filter(is_active=True).values_list(
                "device_token", flat=True
            )
        )

        if tokens:
            notification = PushNotification(
                title=title,
                body=body,
                priority=NotificationPriority.HIGH,
                data={"type": "resource_status", "resource_id": str(instance.id)},
            )
            result = fcm_service.send_to_tokens(tokens, notification)
            logger.info(
                f"Resource status notification sent to user {user.id}: {result}"
            )


@receiver(post_save, sender=Announcement)
def new_announcement(sender, instance, created, **kwargs):
    """
    Send push notification when a new announcement is created.
    """
    if created and instance.is_active:
        title = "📢 New Announcement"
        body = instance.title

        # Send to all active users subscribed to announcements
        # This could be optimized with topic messaging
        notification = PushNotification(
            title=title,
            body=body,
            priority=NotificationPriority.HIGH,
            data={"type": "announcement", "announcement_id": str(instance.id)},
        )

        # For now, send to a topic - users subscribe to this
        result = fcm_service.send_to_topic("announcements", notification)
        logger.info(f"Announcement notification sent: {result}")


@receiver(post_save, sender=Comment)
def new_comment_notification(sender, instance, created, **kwargs):
    """
    Send push notification when someone comments on your resource.
    """
    if created:
        resource = instance.resource
        if not resource or not resource.uploaded_by:
            return

        # Don't notify if commenting on own resource
        if resource.uploaded_by == instance.author:
            return

        user = resource.uploaded_by
        tokens = list(
            user.device_tokens.filter(is_active=True).values_list(
                "device_token", flat=True
            )
        )

        if not tokens:
            return

        title = "💬 New Comment"
        body = f'{instance.author.get_full_name() or instance.author.email} commented on "{resource.title}"'

        notification = PushNotification(
            title=title,
            body=body,
            priority=NotificationPriority.NORMAL,
            data={
                "type": "comment",
                "resource_id": str(resource.id),
                "comment_id": str(instance.id),
            },
        )

        result = fcm_service.send_to_tokens(tokens, notification)
        logger.info(f"Comment notification sent to user {user.id}: {result}")


def send_notification_to_user(
    user, title: str, body: str, notification_type: str = "general", data: dict = None
):
    """
    Helper function to send push notification to a user.

    Args:
        user: User instance
        title: Notification title
        body: Notification body
        notification_type: Type of notification
        data: Additional data payload
    """
    tokens = list(
        user.device_tokens.filter(is_active=True).values_list("device_token", flat=True)
    )

    if not tokens:
        logger.debug(f"No device tokens for user {user.id}")
        return {"success": False, "error": "No device tokens"}

    notification = PushNotification(
        title=title,
        body=body,
        priority=NotificationPriority.HIGH,
        data=data or {"type": notification_type},
    )

    return fcm_service.send_to_tokens(tokens, notification)


def broadcast_to_topic(topic: str, title: str, body: str, data: dict = None):
    """
    Broadcast a notification to all users subscribed to a topic.
    """
    notification = PushNotification(
        title=title, body=body, priority=NotificationPriority.HIGH, data=data or {}
    )

    return fcm_service.send_to_topic(topic, notification)
