"""
Services for notifications app.
"""


from .models import Notification, NotificationType


class NotificationService:
    """Service for creating and managing notifications."""

    @staticmethod
    def _emit_realtime_notification(notification: Notification):
        """Push notification over WebSocket to the recipient group."""
        from .websocket import WebSocketNotificationService

        WebSocketNotificationService.send_notification(
            user_id=notification.recipient_id,
            title=notification.title,
            message=notification.message,
            notification_type=notification.notification_type,
            link=notification.link,
            notification_id=notification.id,
        )

    @staticmethod
    def _emit_global_event(title: str, message: str, priority: str = "normal"):
        """Broadcast moderation/admin relevant events to global admin stream."""
        from .websocket import WebSocketNotificationService

        WebSocketNotificationService.send_global_notification(
            title=title,
            message=message,
            priority=priority,
        )

    @staticmethod
    def _should_send_app_notification(user) -> bool:
        try:
            preferences = user.preferences
        except Exception:
            preferences = None
        return bool(getattr(preferences, "app_notifications", True))

    @staticmethod
    def _should_send_push_notification(user) -> bool:
        try:
            preferences = user.preferences
        except Exception:
            preferences = None
        return bool(getattr(preferences, "push_notifications", True))

    @staticmethod
    def _send_push_to_user(
        user,
        *,
        title: str,
        message: str,
        data: dict | None = None,
        priority: str = "normal",
    ) -> bool:
        if not user or not getattr(user, "is_active", False):
            return False
        if not NotificationService._should_send_push_notification(user):
            return False

        from apps.notifications.fcm import NotificationPriority, PushNotification, fcm_service
        from apps.notifications.models import DeviceToken

        tokens = list(
            DeviceToken.objects.filter(user=user, is_active=True).values_list(
                "device_token", flat=True
            )
        )
        if not tokens:
            return False

        push_priority = (
            NotificationPriority.HIGH if priority == "high" else NotificationPriority.NORMAL
        )
        notification = PushNotification(
            title=title,
            body=message,
            priority=push_priority,
            data=data or {},
        )
        try:
            fcm_service.send_to_tokens(tokens, notification)
            return True
        except Exception:
            return False

    @staticmethod
    def create_notification(
        recipient,
        title,
        message,
        notification_type,
        link="",
        target_resource=None,
        target_comment=None,
    ):
        """
        Create a notification.

        Args:
            recipient: User to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            link: Optional link to related content
            target_resource: Optional related resource
            target_comment: Optional related comment

        Returns:
            Notification: Created notification
        """
        notification = Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            target_resource=target_resource,
            target_comment=target_comment,
        )
        NotificationService._emit_realtime_notification(notification)
        return notification

    @staticmethod
    def notify_resource_approved(resource):
        """Notify user when their resource is approved."""
        notification = NotificationService.create_notification(
            recipient=resource.uploaded_by,
            title="Resource Approved",
            message=f'Your resource "{resource.title}" has been approved and is now live.',
            notification_type=NotificationType.RESOURCE_APPROVED,
            link=f"/resources/{resource.slug}/",
            target_resource=resource,
        )
        NotificationService._emit_global_event(
            title="Resource Approved",
            message=f'"{resource.title}" was approved by moderation.',
            priority="normal",
        )
        return notification

    @staticmethod
    def notify_resource_rejected(resource, reason):
        """Notify user when their resource is rejected."""
        notification = NotificationService.create_notification(
            recipient=resource.uploaded_by,
            title="Resource Rejected",
            message=f'Your resource "{resource.title}" has been rejected. Reason: {reason}',
            notification_type=NotificationType.RESOURCE_REJECTED,
            link=f"/resources/{resource.slug}/",
            target_resource=resource,
        )
        NotificationService._emit_global_event(
            title="Resource Rejected",
            message=f'"{resource.title}" was rejected by moderation.',
            priority="high",
        )
        return notification

    @staticmethod
    def notify_new_comment(comment, resource_owner):
        """Notify resource owner about new comment."""
        if comment.user != resource_owner:
            return NotificationService.create_notification(
                recipient=resource_owner,
                title="New Comment",
                message=f'{comment.user.full_name} commented on "{comment.resource.title}"',
                notification_type=NotificationType.NEW_COMMENT,
                link=f"/resources/{comment.resource.slug}/#comment-{comment.id}",
                target_resource=comment.resource,
                target_comment=comment,
            )

    @staticmethod
    def notify_comment_reply(comment, parent_comment_user):
        """Notify user about reply to their comment."""
        if comment.user != parent_comment_user:
            return NotificationService.create_notification(
                recipient=parent_comment_user,
                title="New Reply",
                message=f'{comment.user.full_name} replied to your comment on "{comment.resource.title}"',
                notification_type=NotificationType.COMMENT_REPLY,
                link=f"/resources/{comment.resource.slug}/#comment-{comment.id}",
                target_resource=comment.resource,
                target_comment=comment,
            )

    @staticmethod
    def notify_new_rating(rating, resource_owner):
        """Notify resource owner about new rating."""
        if rating.user != resource_owner:
            return NotificationService.create_notification(
                recipient=resource_owner,
                title="New Rating",
                message=f'{rating.user.full_name} rated your resource "{rating.resource.title}" with {rating.value} stars',
                notification_type=NotificationType.NEW_RATING,
                link=f"/resources/{rating.resource.slug}/",
                target_resource=rating.resource,
            )

    @staticmethod
    def notify_report_status(report):
        """Notify report submitter about status updates."""
        notification = NotificationService.create_notification(
            recipient=report.reporter,
            title="Report Update",
            message=f'Your report regarding "{report.get_target_title()}" is now {report.status.replace("_", " ")}.',
            notification_type=NotificationType.REPORT_UPDATE,
            link=f"/reports/{report.id}/",
        )

    @staticmethod
    def notify_new_resource_available(resource):
        """
        Notify users interested in the resource's course/unit about new content.
        This is called when a resource is approved and made public.
        """
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get users who might be interested in this resource
        # (users enrolled in the same course or who have downloaded similar resources)
        interested_users = User.objects.filter(
            is_active=True,
            role__iexact='student'
        ).exclude(
            id=resource.uploaded_by_id  # Don't notify the uploader
        )
        
        # Filter by course if available
        if resource.course_id:
            interested_users = interested_users.filter(
                course_id=resource.course_id
            )
        
        # Limit to prevent spamming - notify max 50 users
        interested_users = interested_users[:50]
        
        notification_type = NotificationType.NEW_RESOURCE

        for user in interested_users:
            try:
                if NotificationService._should_send_app_notification(user):
                    NotificationService.create_notification(
                        recipient=user,
                        title="New Resource Available",
                        message=(
                            f'A new {resource.get_resource_type_display().lower()} '
                            f'"{resource.title}" is now available!'
                        ),
                        notification_type=notification_type,
                        link=f"/resources/{resource.slug}/",
                        target_resource=resource,
                    )
                NotificationService._send_push_to_user(
                    user,
                    title="New Resource Available",
                    message=(
                        f'A new {resource.get_resource_type_display().lower()} '
                        f'"{resource.title}" is now available!'
                    ),
                    data={
                        "type": "new_resource",
                        "resource_id": str(resource.id),
                    },
                )
            except Exception:
                pass  # Don't fail if one notification fails

    @staticmethod
    def notify_resource_updated(resource, updated_fields):
        """
        Notify users when a resource they bookmarked or downloaded is updated.
        """
        from apps.bookmarks.models import Bookmark
        from apps.downloads.models import Download
        
        # Get users who bookmarked or downloaded this resource
        user_ids = set()
        
        bookmarks = Bookmark.objects.filter(
            resource=resource,
            user__is_active=True
        ).values_list('user_id', flat=True)[:20]
        user_ids.update(bookmarks)
        
        downloads = Download.objects.filter(
            resource=resource,
            user__is_active=True
        ).values_list('user_id', flat=True)[:20]
        user_ids.update(downloads)
        
        # Remove the uploader
        user_ids.discard(resource.uploaded_by_id)
        
        if not user_ids:
            return
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        users = User.objects.filter(id__in=user_ids, is_active=True)[:30]
        
        for user in users:
            try:
                NotificationService.create_notification(
                    recipient=user,
                    title="Resource Updated",
                    message=f'"{resource.title}" has been updated.',
                    notification_type=NotificationType.RESOURCE_UPDATED,
                    link=f"/resources/{resource.slug}/",
                    target_resource=resource,
                )
            except Exception:
                pass
        return

    @staticmethod
    def notify_resource_liked(favorite):
        """Notify resource owner when their resource is liked."""
        resource = getattr(favorite, "resource", None)
        if not resource or not getattr(resource, "uploaded_by", None):
            return None

        owner = resource.uploaded_by
        liker = getattr(favorite, "user", None)
        if not liker or owner.id == liker.id:
            return None

        liker_name = liker.get_full_name() if hasattr(liker, "get_full_name") else ""
        display_name = liker_name.strip() or getattr(liker, "email", "Someone")
        title = "New Like"
        message = f'{display_name} liked your resource "{resource.title}"'

        notification = None
        if NotificationService._should_send_app_notification(owner):
            notification = NotificationService.create_notification(
                recipient=owner,
                title=title,
                message=message,
                notification_type=NotificationType.RESOURCE_LIKED,
                link=f"/resources/{resource.slug}/",
                target_resource=resource,
            )

        NotificationService._send_push_to_user(
            owner,
            title=title,
            message=message,
            data={
                "type": "resource_liked",
                "resource_id": str(resource.id),
            },
        )

        return notification

    @staticmethod
    def notify_announcement(recipients, title, message, link=""):
        """
        Send announcement to multiple users.

        Args:
            recipients: QuerySet or list of users
            title: Announcement title
            message: Announcement message
            link: Optional link

        Returns:
            int: Number of notifications created
        """
        notifications = []
        for user in recipients:
            notifications.append(
                Notification(
                    recipient=user,
                    title=title,
                    message=message,
                    notification_type=NotificationType.ANNOUNCEMENT,
                    link=link,
                )
            )
        created_notifications = Notification.objects.bulk_create(notifications)
        for notification in created_notifications:
            NotificationService._emit_realtime_notification(notification)
        NotificationService._emit_global_event(
            title="New Announcement",
            message=title,
            priority="normal",
        )
        return created_notifications

    @staticmethod
    def notify_resource_shared_with_user(recipient, sender, resource, message=""):
        """
        Notify a user when a resource is shared with them.

        Args:
            recipient: User to notify
            sender: User who shared the resource
            resource: The shared resource
            message: Optional custom message

        Returns:
            Notification: Created notification
        """
        sender_name = sender.get_full_name() or sender.username
        default_message = f"{sender_name} shared a resource with you: {resource.title}"
        if message:
            default_message = f"{sender_name} said: {message}"

        return NotificationService.create_notification(
            recipient=recipient,
            title="Resource Shared With You",
            message=default_message,
            notification_type=NotificationType.RESOURCE_SHARED_WITH_USER,
            link=f"/resources/{resource.slug}/",
            target_resource=resource,
        )

    @staticmethod
    def notify_resource_shared_to_group(recipients, sender, resource, group_name, message=""):
        """
        Notify multiple users (group members) when a resource is shared with their group.

        Args:
            recipients: QuerySet or list of users to notify
            sender: User who shared the resource
            resource: The shared resource
            group_name: Name of the study group
            message: Optional custom message

        Returns:
            list: Created notifications
        """
        sender_name = sender.get_full_name() or sender.username
        default_message = f"{sender_name} shared a resource with the group '{group_name}': {resource.title}"
        if message:
            default_message = f"{sender_name} said in '{group_name}': {message}"

        notifications = []
        for user in recipients:
            # Don't notify the sender
            if user.id != sender.id:
                notifications.append(
                    Notification(
                        recipient=user,
                        title="Resource Shared to Study Group",
                        message=default_message,
                        notification_type=NotificationType.RESOURCE_SHARED_TO_GROUP,
                        link=f"/resources/{resource.slug}/",
                        target_resource=resource,
                    )
                )

        if notifications:
            created_notifications = Notification.objects.bulk_create(notifications)
            for notification in created_notifications:
                NotificationService._emit_realtime_notification(notification)
            return created_notifications
        return []

    @staticmethod
    def get_unread_count(user):
        """Get count of unread notifications for a user."""
        return Notification.objects.filter(recipient=user, is_read=False).count()

    @staticmethod
    def get_recent_notifications(user, limit=5):
        """Get recent notifications for a user."""
        return Notification.objects.filter(recipient=user)[:limit]


class AdminNotificationService:
    """Service for admin-specific notifications and alerts."""

    @staticmethod
    def notify_admins(
        title: str,
        message: str,
        notification_type: str,
        priority: str = "medium",
        link: str = "",
        target_resource=None,
    ):
        """
        Send notification to all admin users.
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification (from NotificationType)
            priority: Priority level (low, medium, high, urgent)
            link: Optional link to related content
            target_resource: Optional related resource
        """
        from django.conf import settings
        from django.contrib.auth import get_user_model

        User = get_user_model()
        
        # Get all staff users (admins)
        admins = User.objects.filter(
            is_staff=True, is_active=True
        ).values_list('id', flat=True)

        if not admins:
            return []

        notifications = []
        for admin_id in admins:
            notifications.append(
                Notification(
                    recipient_id=admin_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    is_admin_notification=True,
                    link=link,
                    target_resource=target_resource,
                )
            )

        created_notifications = Notification.objects.bulk_create(notifications)
        
        # Emit real-time notification to all admins
        for notification in created_notifications:
            NotificationService._emit_realtime_notification(notification)
        
        # Also emit global admin notification
        NotificationService._emit_global_event(
            title=title,
            message=message,
            priority=priority,
        )

        return created_notifications

    @staticmethod
    def notify_new_user_signup(user):
        """Notify admins when a new user signs up."""
        return AdminNotificationService.notify_admins(
            title="New User Signup",
            message=f"New user {user.get_full_name() or user.email} has registered. "
                    f"Email: {user.email}",
            notification_type=NotificationType.ADMIN_NEW_USER_SIGNUP,
            priority="medium",
            link=f"/admin/users/{user.id}/change/",
        )

    @staticmethod
    def notify_user_report(report):
        """Notify admins when a user report is submitted."""
        return AdminNotificationService.notify_admins(
            title="User Report Received",
            message=f"A new user report has been submitted. Reason: {report.get('reason', 'Unknown')}",
            notification_type=NotificationType.ADMIN_USER_REPORT,
            priority="high",
            link=f"/admin/reports/{report.get('id', '')}/",
        )

    @staticmethod
    def notify_content_report(report):
        """Notify admins when content is reported."""
        return AdminNotificationService.notify_admins(
            title="Content Report Received",
            message=f"Content has been reported. Reason: {report.get('reason', 'Unknown')}",
            notification_type=NotificationType.ADMIN_CONTENT_REPORT,
            priority="high",
            link=f"/admin/reports/{report.get('id', '')}/",
        )

    @staticmethod
    def notify_pending_moderation(resource):
        """Notify admins when a resource needs moderation."""
        return AdminNotificationService.notify_admins(
            title="Resource Pending Moderation",
            message=f"Resource '{resource.title}' requires moderation review.",
            notification_type=NotificationType.ADMIN_RESOURCE_PENDING_MODERATION,
            priority="medium",
            link=f"/admin/resources/{resource.slug}/change/",
            target_resource=resource,
        )

    @staticmethod
    def notify_suspicious_activity(activity_type: str, details: str):
        """Notify admins of suspicious activity."""
        return AdminNotificationService.notify_admins(
            title="Suspicious Activity Detected",
            message=f"{activity_type}: {details}",
            notification_type=NotificationType.ADMIN_SUSPICIOUS_ACTIVITY,
            priority="urgent",
            link="/admin/security/",
        )

    @staticmethod
    def notify_system_alert(alert_type: str, message: str, severity: str = "high"):
        """Notify admins of system alerts."""
        return AdminNotificationService.notify_admins(
            title=f"System Alert: {alert_type}",
            message=message,
            notification_type=NotificationType.ADMIN_SYSTEM_ALERT,
            priority=severity,
            link="/admin/system/health/",
        )

    @staticmethod
    def notify_api_threshold_warning(endpoint: str, current: int, threshold: int):
        """Notify admins when API usage exceeds threshold."""
        return AdminNotificationService.notify_admins(
            title="API Threshold Warning",
            message=f"API endpoint '{endpoint}' has exceeded {threshold} requests. "
                    f"Current: {current} requests.",
            notification_type=NotificationType.ADMIN_API_THRESHOLD_WARNING,
            priority="medium",
            link="/admin/analytics/api-usage/",
        )

    @staticmethod
    def notify_storage_warning(percentage: float):
        """Notify admins of storage warning."""
        return AdminNotificationService.notify_admins(
            title="Storage Warning",
            message=f"Storage usage is at {percentage:.1f}%. Consider cleanup or expansion.",
            notification_type=NotificationType.ADMIN_STORAGE_WARNING,
            priority="high",
            link="/admin/system/storage/",
        )

    @staticmethod
    def notify_bulk_operation_complete(operation: str, success_count: int, fail_count: int):
        """Notify admins when bulk operation completes."""
        status = "completed successfully" if fail_count == 0 else "completed with errors"
        return AdminNotificationService.notify_admins(
            title="Bulk Operation Complete",
            message=f"Bulk {operation} {status}. Success: {success_count}, Failed: {fail_count}.",
            notification_type=NotificationType.ADMIN_BULK_OPERATION_COMPLETE,
            priority="low",
            link="/admin/bulk-operations/",
        )

    @staticmethod
    def get_admin_notifications(admin_user, unread_only=False, limit=50):
        """Get notifications for admin user."""
        queryset = Notification.objects.filter(
            recipient=admin_user,
            is_admin_notification=True,
        )
        
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        return queryset[:limit]

    @staticmethod
    def get_admin_notification_stats(admin_user):
        """Get notification statistics for admin user."""
        total = Notification.objects.filter(
            recipient=admin_user,
            is_admin_notification=True,
        ).count()
        
        unread = Notification.objects.filter(
            recipient=admin_user,
            is_admin_notification=True,
            is_read=False,
        ).count()
        
        urgent = Notification.objects.filter(
            recipient=admin_user,
            is_admin_notification=True,
            is_read=False,
            priority__in=['high', 'urgent'],
        ).count()
        
        return {
            'total': total,
            'unread': unread,
            'urgent': urgent,
        }
