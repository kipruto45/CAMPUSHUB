"""
WebSocket notification service.
Provides easy interface to send real-time notifications to users.
"""

from typing import List

from channels.layers import get_channel_layer
from django.utils import timezone


class WebSocketNotificationService:
    """
    Service for sending real-time notifications via WebSockets.
    """

    @staticmethod
    def send_notification(
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "info",
        link: str = None,
        notification_id: int = None,
    ) -> bool:
        """
        Send notification to a specific user via WebSocket.

        Args:
            user_id: ID of the recipient user
            title: Notification title
            message: Notification message body
            notification_type: Type of notification (info, success, warning, error)
            link: Optional URL to redirect to
            notification_id: ID of the notification in database

        Returns:
            True if message was sent successfully
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f"notifications_{user_id}"

            # Prepare notification data
            notification_data = {
                "type": "notification_message",
                "id": notification_id,
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "timestamp": timezone.now().isoformat(),
                "link": link,
                "read": False,
            }

            # Send to user's notification group
            from asgiref.sync import async_to_sync

            async_to_sync(channel_layer.group_send)(group_name, notification_data)

            return True
        except Exception as e:
            # Log error but don't fail - WebSocket is optional
            import logging

            logging.warning(f"WebSocket notification failed: {e}")
            return False

    @staticmethod
    def send_bulk_notifications(
        user_ids: List[int],
        title: str,
        message: str,
        notification_type: str = "info",
        link: str = None,
    ) -> int:
        """
        Send notification to multiple users.

        Args:
            user_ids: List of recipient user IDs
            title: Notification title
            message: Notification message body
            notification_type: Type of notification
            link: Optional URL to redirect to

        Returns:
            Number of successful notifications sent
        """
        success_count = 0
        for user_id in user_ids:
            if WebSocketNotificationService.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link,
            ):
                success_count += 1

        return success_count

    @staticmethod
    def send_global_notification(
        title: str, message: str, priority: str = "normal"
    ) -> bool:
        """
        Send global/platform-wide notification to all admins.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high, critical)

        Returns:
            True if message was sent successfully
        """
        try:
            channel_layer = get_channel_layer()

            notification_data = {
                "type": "global_notification",
                "title": title,
                "message": message,
                "priority": priority,
                "timestamp": timezone.now().isoformat(),
            }

            from asgiref.sync import async_to_sync

            async_to_sync(channel_layer.group_send)(
                "global_notifications", notification_data
            )

            return True
        except Exception as e:
            import logging

            logging.warning(f"Global WebSocket notification failed: {e}")
            return False

    @staticmethod
    def send_activity_update(
        *,
        activity_type: str,
        user=None,
        resource=None,
        personal_file=None,
        metadata: dict | None = None,
    ) -> bool:
        """
        Send activity update to admin activity stream subscribers.
        """
        try:
            channel_layer = get_channel_layer()
            from asgiref.sync import async_to_sync

            payload = {
                "type": "activity_update",
                "activity_type": activity_type,
                "user": (
                    {
                        "id": user.id,
                        "name": (
                            user.get_full_name()
                            if hasattr(user, "get_full_name")
                            else str(user)
                        ),
                    }
                    if user
                    else None
                ),
                "resource": (
                    {
                        "id": str(resource.id),
                        "title": resource.title,
                    }
                    if resource
                    else None
                ),
                "personal_file": (
                    {
                        "id": str(personal_file.id),
                        "title": personal_file.title,
                    }
                    if personal_file
                    else None
                ),
                "metadata": metadata or {},
                "timestamp": timezone.now().isoformat(),
            }

            async_to_sync(channel_layer.group_send)("activity_stream", payload)
            return True
        except Exception as e:
            import logging

            logging.warning(f"Activity WebSocket update failed: {e}")
            return False

    @staticmethod
    def notify_resource_uploaded(user_id: int, resource_title: str, resource_id: int):
        """Notify user that their resource was uploaded successfully."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="Resource Uploaded",
            message=f'Your resource "{resource_title}" has been uploaded successfully.',
            notification_type="success",
            link=f"/resources/{resource_id}",
        )

    @staticmethod
    def notify_resource_approved(user_id: int, resource_title: str, resource_id: int):
        """Notify user that their resource was approved."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="Resource Approved",
            message=f'Your resource "{resource_title}" has been approved and is now visible.',
            notification_type="success",
            link=f"/resources/{resource_id}",
        )

    @staticmethod
    def notify_resource_rejected(user_id: int, resource_title: str, reason: str):
        """Notify user that their resource was rejected."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="Resource Rejected",
            message=f'Your resource "{resource_title}" was rejected. Reason: {reason}',
            notification_type="warning",
            link="/library",
        )

    @staticmethod
    def notify_new_comment(user_id: int, resource_title: str, commenter_name: str):
        """Notify user of a new comment on their resource."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="New Comment",
            message=f'{commenter_name} commented on "{resource_title}"',
            notification_type="info",
            link="/resources",
        )

    @staticmethod
    def notify_new_rating(user_id: int, resource_title: str, rating: int):
        """Notify user of a new rating on their resource."""
        stars = "⭐" * rating
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="New Rating",
            message=f'Your resource "{resource_title}" received {stars} rating',
            notification_type="info",
            link="/resources",
        )

    @staticmethod
    def notify_report_resolved(user_id: int, resource_title: str, resolution: str):
        """Notify user that their report was resolved."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="Report Resolved",
            message=f'Your report on "{resource_title}" has been resolved: {resolution}',
            notification_type="success",
            link="/resources",
        )

    @staticmethod
    def notify_storage_warning(user_id: int, storage_percent: int):
        """Notify user of low storage."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="Storage Warning",
            message=f"You have used {storage_percent}% of your storage quota. Consider deleting some files.",
            notification_type="warning",
            link="/library/storage",
        )

    @staticmethod
    def notify_new_announcement(user_id: int, title: str):
        """Notify user of a new announcement."""
        return WebSocketNotificationService.send_notification(
            user_id=user_id,
            title="New Announcement",
            message=f"New announcement: {title}",
            notification_type="info",
            link="/announcements",
        )
