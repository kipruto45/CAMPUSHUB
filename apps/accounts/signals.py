"""
Signals for accounts app.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create resources when a new user is created.

    Automations:
    - Auto-create user storage tracker
    - Auto-create personal library folders
    """
    if created:
        from apps.gamification.services import GamificationService
        # Create user storage tracker
        from apps.resources.models import UserStorage

        UserStorage.objects.get_or_create(user=instance)
        try:
            GamificationService.initialize_user_stats(instance)
        except Exception:
            logger.exception(
                "Failed to initialize gamification stats for user_id=%s",
                instance.pk,
            )

        # Create personal library folders
        _create_personal_library(instance)

        # Send welcome notification
        _send_welcome_notification(instance)

        if instance.is_verified:
            try:
                GamificationService.record_email_verification(instance)
            except Exception:
                logger.exception(
                    "Failed to record email verification gamification for user_id=%s",
                    instance.pk,
                )


def _create_personal_library(user):
    """
    Auto-create starter folders on signup.
    Creates default folder structure: Notes, Assignments, Books, Other
    """
    from apps.resources.models import PersonalFolder

    default_folders = [
        {"name": "Notes", "color": "#3B82F6"},
        {"name": "Assignments", "color": "#10B981"},
        {"name": "Books", "color": "#8B5CF6"},
        {"name": "Other", "color": "#6B7280"},
    ]

    for folder_data in default_folders:
        PersonalFolder.objects.get_or_create(
            user=user,
            name=folder_data["name"],
            defaults={"color": folder_data["color"]},
        )


def _send_welcome_notification(user):
    """Send welcome notification to new user."""
    try:
        from apps.notifications.services import NotificationService

        NotificationService.create_notification(
            recipient=user,
            title="Welcome to CampusHub",
            message="Your account is ready. Complete your profile to get better recommendations.",
            notification_type="system",
            link="/dashboard/",
        )
    except Exception:
        pass


def log_user_activity(user, action, description="", request=None):
    """
    Log user activity.

    Used for:
    - Track last login
    - Track profile changes
    - Feed suspicious login detection checks
    """
    ip_address = None
    user_agent = ""

    if request:
        from apps.core.utils import get_client_ip, get_user_agent

        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

    from .models import UserActivity

    UserActivity.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
    )
