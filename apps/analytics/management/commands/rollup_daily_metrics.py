"""
Create or update DailyMetric rollups from AnalyticsEvent.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.analytics.models import AnalyticsEvent, DailyMetric
from apps.accounts.models import User
from apps.resources.models import Resource


class Command(BaseCommand):
    help = "Aggregate AnalyticsEvent into DailyMetric records (idempotent per day)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of past days to roll up (including today)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        today = date.today()
        for offset in range(days):
            target = today - timedelta(days=offset)
            self._rollup_day(target)
        self.stdout.write(self.style.SUCCESS(f"Rolled up {days} day(s)."))

    def _rollup_day(self, target_date: date):
        start = target_date
        end = target_date + timedelta(days=1)

        events = AnalyticsEvent.objects.filter(timestamp__date=target_date)
        counts = events.values("event_type").annotate(total=Count("id"))

        total_users = User.objects.filter(date_joined__lte=end).count()
        new_signups = User.objects.filter(date_joined__date=target_date).count()
        total_resources = Resource.objects.filter(created_at__lte=end).count()
        new_resources = Resource.objects.filter(created_at__date=target_date).count()

        metric, _ = DailyMetric.objects.get_or_create(date=target_date)
        metric.total_users = total_users
        metric.new_signups = new_signups
        metric.total_resources = total_resources
        metric.new_resources = new_resources

        # Simple engagement counts
        metric.total_views = next((c["total"] for c in counts if c["event_type"] == "resource_view"), 0)
        metric.total_downloads = next((c["total"] for c in counts if c["event_type"] == "resource_download"), 0)
        metric.total_bookmarks = next((c["total"] for c in counts if c["event_type"] == "bookmark"), 0)
        metric.total_comments = next((c["total"] for c in counts if c["event_type"] == "comment"), 0)
        metric.total_ratings = next((c["total"] for c in counts if c["event_type"] == "rating"), 0)
        metric.messages_sent = next((c["total"] for c in counts if c["event_type"] == "chat_message"), 0)
        metric.save()
