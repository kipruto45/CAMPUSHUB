"""
Celery tasks for notifications app.
"""

from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import Notification, NotificationType


@shared_task
def send_daily_notifications():
    """Send in-app daily notification summary to active users."""
    since = timezone.now() - timedelta(days=1)
    User = get_user_model()
    recipients = User.objects.filter(is_active=True)

    sent = 0
    for user in recipients.iterator():
        unread_count = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
        recent_count = Notification.objects.filter(
            recipient=user, created_at__gte=since
        ).count()
        if unread_count == 0 and recent_count == 0:
            continue

        Notification.objects.create(
            recipient=user,
            title="Daily CampusHub Summary",
            message=(
                f"You have {unread_count} unread notifications and "
                f"{recent_count} updates from the last 24 hours."
            ),
            notification_type=NotificationType.SYSTEM,
            link="/notifications/",
        )
        sent += 1

    return f"Daily summaries sent: {sent}"


@shared_task
def send_inactivity_reminders():
    """Send engagement reminders to users who have not visited today."""
    now = timezone.localtime(timezone.now())
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    User = get_user_model()
    recipients = (
        User.objects.filter(is_active=True, role__iexact="student")
        .select_related("preferences")
        .only("id", "email", "last_activity", "last_login")
    )

    sent = 0
    for user in recipients.iterator():
        last_activity = user.last_activity or user.last_login
        if last_activity and last_activity >= day_start:
            continue

        already_sent = Notification.objects.filter(
            recipient=user,
            notification_type=NotificationType.INACTIVITY_REMINDER,
            created_at__gte=day_start,
        ).exists()
        if already_sent:
            continue

        title = "We miss you on CampusHub"
        message = "You haven't visited CampusHub today. New resources are waiting."

        try:
            from apps.notifications.services import NotificationService

            if NotificationService._should_send_app_notification(user):
                NotificationService.create_notification(
                    recipient=user,
                    title=title,
                    message=message,
                    notification_type=NotificationType.INACTIVITY_REMINDER,
                    link="/(student)/tabs/home",
                )

            NotificationService._send_push_to_user(
                user,
                title=title,
                message=message,
                data={"type": "inactivity_reminder"},
            )
            sent += 1
        except Exception:
            continue

    return f"Inactivity reminders sent: {sent}"
