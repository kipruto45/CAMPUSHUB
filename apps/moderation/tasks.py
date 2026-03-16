"""Celery tasks for moderation automation."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.reports.models import Report
from apps.resources.models import Resource

from .services import ModerationService


@shared_task
def notify_stale_pending_resources(days=2):
    """Notify moderation team about old pending resources."""
    cutoff = timezone.now() - timedelta(days=days)
    stale_pending = Resource.objects.filter(
        status="pending", created_at__lt=cutoff
    ).order_by("created_at")[:50]
    count = stale_pending.count()
    if not count:
        return "No stale pending resources."

    oldest = stale_pending.first()
    ModerationService.notify_moderation_team(
        title="Stale Pending Queue Alert",
        message=f'{count} resources have been pending for more than {days} days. Oldest: "{oldest.title}".',
        link="/moderation/pending-resources/",
    )
    return f"Notified moderation team about {count} stale resources."


@shared_task
def notify_open_reports(days=1):
    """Notify moderation team about unresolved open reports."""
    cutoff = timezone.now() - timedelta(days=days)
    open_reports = Report.objects.filter(status="open", created_at__lt=cutoff).order_by(
        "created_at"
    )[:100]
    count = open_reports.count()
    if not count:
        return "No stale open reports."

    ModerationService.notify_moderation_team(
        title="Open Reports Alert",
        message=f"{count} reports are still open after {days} day(s).",
        link="/reports/?status=open",
    )
    return f"Notified moderation team about {count} open reports."
