"""
Signals for reports app.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.moderation.services import ModerationService

from .models import Report


@receiver(post_save, sender=Report)
def report_created(sender, instance, created, **kwargs):
    """Trigger moderation automation when new reports are submitted."""
    if created:
        ModerationService.handle_new_report(instance)
