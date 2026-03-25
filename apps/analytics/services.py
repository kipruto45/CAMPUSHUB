"""
Analytics services for tracking, aggregation, and learning insights.
"""

import logging
import uuid
from datetime import date, timedelta
from typing import List, Optional
from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import ExtractHour, TruncDay
from django.utils import timezone
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for tracking and aggregating analytics."""

    @staticmethod
    def _normalize_period(period: str) -> int:
        mapping = {
            "day": 1,
            "week": 7,
            "month": 30,
            "quarter": 90,
            "year": 365,
        }
        return mapping.get(str(period or "").lower(), 30)

    @staticmethod
    def track_event(
        user,
        event_type: str,
        event_name: str = None,
        resource_id: str = None,
        course_id: str = None,
        unit_id: str = None,
        properties: dict = None,
        session_id: str = None,
        **kwargs
    ):
        """Track a user event."""
        from apps.analytics.models import AnalyticsEvent

        return AnalyticsEvent.objects.create(
            user=user,
            session_id=session_id or "",
            event_type=event_type,
            event_name=event_name or event_type,
            resource_id=resource_id,
            course_id=course_id,
            unit_id=unit_id,
            properties=properties or {},
            **kwargs
        )

    @staticmethod
    def get_user_activity_timeline(user, days: int = 30) -> List[dict]:
        """Get user's activity timeline for the last N days."""
        from apps.analytics.models import AnalyticsEvent

        start_date = timezone.now() - timedelta(days=days)
        
        events = AnalyticsEvent.objects.filter(
            user=user,
            timestamp__gte=start_date
        ).values('event_type', 'timestamp').order_by('-timestamp')

        # Group by day
        timeline = {}
        for event in events:
            day = event['timestamp'].date().isoformat()
            if day not in timeline:
                timeline[day] = []
            timeline[day].append(event['event_type'])

        return timeline

    @staticmethod
    def get_popular_resources(days: int = 7, limit: int = 10) -> List[dict]:
        """Get most popular resources in the last N days."""
        from apps.analytics.models import AnalyticsEvent

        start_date = timezone.now() - timedelta(days=days)

        # Count downloads and views
        downloads = AnalyticsEvent.objects.filter(
            event_type='resource_download',
            timestamp__gte=start_date
        ).values('resource_id').annotate(count=Count('id')).order_by('-count')

        views = AnalyticsEvent.objects.filter(
            event_type='resource_view',
            timestamp__gte=start_date
        ).values('resource_id').annotate(count=Count('id')).order_by('-count')

        return {
            'downloads': list(downloads[:limit]),
            'views': list(views[:limit]),
        }

    @staticmethod
    def get_admin_dashboard_payload(period: str = "month") -> dict:
        """Build the admin dashboard payload consumed by analytics views."""
        from django.contrib.auth import get_user_model
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        User = get_user_model()
        days = AnalyticsService._normalize_period(period)
        resources_qs = Resource.objects.filter(is_deleted=False)
        total_resources = resources_qs.count()
        total_downloads = Download.objects.filter(resource__isnull=False).count()
        total_storage_used = resources_qs.aggregate(total=Sum("file_size")).get("total") or 0
        active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count()

        top_resources = list(
            resources_qs.filter(status="approved")
            .order_by("-download_count", "-view_count", "-created_at")
            .values("id", "title", "download_count", "view_count")[:5]
        )
        resource_type_counts = list(
            resources_qs.values("resource_type")
            .annotate(count=Count("id"))
            .order_by("resource_type")
        )
        resource_types = [
            {
                "type": row["resource_type"],
                "count": row["count"],
                "percentage": round((row["count"] / total_resources) * 100, 1)
                if total_resources
                else 0.0,
            }
            for row in resource_type_counts
        ]

        payload = {
            "period": period,
            "summary": AnalyticsService.get_admin_dashboard_stats(),
            "platform_health": AnalyticsService.get_platform_health(),
            "content_trends": AnalyticsService.get_popular_content_trends(days),
            "top_contributors": AnalyticsService.get_top_contributors(limit=5),
            "downloads_chart": DashboardChartService.get_downloads_chart_data(days),
            "resource_types_chart": DashboardChartService.get_resource_types_chart_data(),
            "resources_by_course": list(AnalyticsService.get_resources_by_course()),
            "upload_trends": list(AnalyticsService.get_daily_upload_trends(days)),
            "download_trends": list(AnalyticsService.get_daily_download_trends(days)),
            # Legacy UI-ready analytics payload keys.
            "overview": {
                "total_users": User.objects.count(),
                "total_resources": total_resources,
                "total_downloads": total_downloads,
                "total_uploads": total_resources,
                "active_users": active_users,
                "storage_used": int(total_storage_used or 0),
            },
            "trends": {
                "uploads": list(AnalyticsService.get_daily_upload_trends(days)),
                "downloads": list(AnalyticsService.get_daily_download_trends(days)),
            },
            "top_resources": top_resources,
            "resource_types": resource_types,
        }
        # Keep legacy dashboard keys while exposing the richer payload.
        payload.update(AnalyticsService.get_dashboard_stats())
        return payload

    @staticmethod
    def get_dashboard_stats() -> dict:
        """Legacy dashboard summary shape used by tests and older clients."""
        from django.contrib.auth import get_user_model
        from apps.resources.models import Resource
        from apps.downloads.models import Download

        User = get_user_model()
        return {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
            },
            "resources": {
                "total": Resource.objects.count(),
                "approved": Resource.objects.filter(status="approved").count(),
                "pending": Resource.objects.filter(status="pending").count(),
            },
            "downloads": {
                "total": Download.objects.filter(resource__isnull=False).count(),
            },
        }

    @staticmethod
    def get_user_activity_summary(user, days: int = 30) -> dict:
        """Return a lightweight activity summary for a user."""
        from apps.analytics.models import AnalyticsEvent, UserActivitySummary
        from apps.activity.models import RecentActivity
        from apps.bookmarks.models import Bookmark
        from apps.comments.models import Comment
        from apps.downloads.models import Download
        from apps.favorites.models import Favorite
        from apps.ratings.models import Rating
        from apps.resources.models import Resource

        start_date = timezone.now() - timedelta(days=days)
        events = AnalyticsEvent.objects.filter(user=user, timestamp__gte=start_date)
        counts = {
            row["event_type"]: row["count"]
            for row in events.values("event_type").annotate(count=Count("id"))
        }
        downloads_count = Download.objects.filter(user=user, created_at__gte=start_date).count()
        bookmarks_count = Bookmark.objects.filter(user=user, created_at__gte=start_date).count()
        favorites_count = Favorite.objects.filter(user=user, created_at__gte=start_date).count()
        comments_count = Comment.objects.filter(
            user=user,
            created_at__gte=start_date,
            is_deleted=False,
        ).count()
        ratings_count = Rating.objects.filter(user=user, created_at__gte=start_date).count()
        uploads_count = Resource.objects.filter(
            uploaded_by=user,
            created_at__gte=start_date,
            is_deleted=False,
        ).count()
        recent_activities_count = RecentActivity.objects.filter(
            user=user,
            created_at__gte=start_date,
        ).count()
        latest_summary = (
            UserActivitySummary.objects.filter(user=user).order_by("-period_start").first()
        )

        return {
            "days": days,
            "total_events": events.count(),
            "event_counts": counts,
            "downloads": downloads_count,
            "resource_views": counts.get("resource_view", 0),
            "searches": counts.get("search", 0),
            "uploads": uploads_count,
            "bookmarks": bookmarks_count,
            "favorites": favorites_count,
            "comments": comments_count,
            "ratings": ratings_count,
            "recent_activities": recent_activities_count,
            "last_active": latest_summary.last_active.isoformat()
            if latest_summary and latest_summary.last_active
            else None,
            "current_streak_days": latest_summary.current_streak_days if latest_summary else 0,
            "longest_streak_days": latest_summary.longest_streak_days if latest_summary else 0,
        }

    @staticmethod
    def get_user_engagement_score(user) -> float:
        """Return the predictive engagement score for a user."""
        from apps.core.predictive_analytics import PredictiveAnalyticsService

        try:
            result = PredictiveAnalyticsService.predict_user_engagement(user.id)
            score = float(result.score)
            return round(max(0.0, min(score, 100.0)), 2)
        except Exception:  # pragma: no cover - defensive fallback
            summary = AnalyticsService.get_user_activity_summary(user, days=30)
            activity_weight = (
                summary.get("uploads", 0)
                + summary.get("downloads", 0)
                + summary.get("bookmarks", 0)
                + summary.get("favorites", 0)
                + summary.get("comments", 0)
                + summary.get("ratings", 0)
                + summary.get("recent_activities", 0)
            )
            fallback_score = max(1.0, min(100.0, activity_weight * 5.0))
            return round(fallback_score, 2)

    @staticmethod
    def get_user_demographics() -> dict:
        """Aggregate high-level user demographics for admin dashboards."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        active_users = User.objects.filter(is_active=True)

        role_distribution = list(
            active_users.values("role").annotate(count=Count("id")).order_by("-count")
        )
        faculty_distribution = list(
            active_users.exclude(faculty__isnull=True)
            .values("faculty__id", "faculty__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        department_distribution = list(
            active_users.exclude(department__isnull=True)
            .values("department__id", "department__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_faculty = list(
            active_users.exclude(faculty__isnull=True)
            .values("faculty__id", "faculty__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_course = list(
            active_users.exclude(course__isnull=True)
            .values("course__id", "course__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_year = list(
            active_users.exclude(year_of_study__isnull=True)
            .values("year_of_study")
            .annotate(count=Count("id"))
            .order_by("year_of_study")
        )

        return {
            "total_users": active_users.count(),
            "role_distribution": role_distribution,
            "faculty_distribution": faculty_distribution,
            "department_distribution": department_distribution,
            "verified_users": active_users.filter(is_verified=True).count(),
            # Backward-compatible aliases expected by older consumers.
            "by_faculty": by_faculty,
            "by_course": by_course,
            "by_year": by_year,
        }

    @staticmethod
    def get_platform_health() -> dict:
        """Return core platform health counters."""
        from django.contrib.auth import get_user_model
        from apps.analytics.models import AnalyticsEvent, DailyMetric
        from apps.resources.models import Resource

        User = get_user_model()
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        latest_metric = DailyMetric.objects.order_by("-date").first()

        users = {
            "total": User.objects.filter(is_active=True).count(),
            "active_7d": User.objects.filter(last_login__gte=seven_days_ago).count(),
        }
        resources = {
            "total": Resource.objects.count(),
            "pending": Resource.objects.filter(status="pending").count(),
        }
        activity = {
            "recent_events": AnalyticsEvent.objects.filter(timestamp__gte=seven_days_ago).count(),
            "latest_daily_metric": latest_metric.date.isoformat() if latest_metric else None,
        }
        return {
            "users": users,
            "resources": resources,
            "activity": activity,
            # Legacy flat keys kept for compatibility.
            "total_users": users["total"],
            "active_users_7d": users["active_7d"],
            "total_resources": resources["total"],
            "pending_resources": resources["pending"],
            "recent_events": activity["recent_events"],
            "latest_daily_metric": activity["latest_daily_metric"],
        }

    @staticmethod
    def get_resource_analytics(resource_id: str) -> Optional[dict]:
        """Return analytics details for a single resource."""
        from apps.analytics.models import AnalyticsEvent
        from apps.resources.models import Resource

        try:
            normalized_resource_id = str(uuid.UUID(str(resource_id)))
        except (TypeError, ValueError, AttributeError):
            return None

        resource = (
            Resource.all_objects.filter(id=normalized_resource_id)
            .select_related("uploaded_by", "course", "unit")
            .first()
        )
        if resource is None:
            return None

        downloads_total = resource.downloads.count()
        ratings_total = resource.ratings.count()
        ratings_average = (
            resource.ratings.aggregate(avg=Avg("value")).get("avg") if ratings_total else 0
        )
        comments_total = resource.comments.filter(is_deleted=False).count()

        event_counts = {
            row["event_type"]: row["count"]
            for row in AnalyticsEvent.objects.filter(resource_id=resource.id)
            .values("event_type")
            .annotate(count=Count("id"))
        }

        return {
            "id": str(resource.id),
            "title": resource.title,
            "status": resource.status,
            "resource_type": resource.resource_type,
            "uploaded_by": resource.uploaded_by_id,
            "course_id": str(resource.course_id) if resource.course_id else None,
            "unit_id": str(resource.unit_id) if resource.unit_id else None,
            "view_count": resource.view_count,
            "download_count": resource.download_count,
            "share_count": resource.share_count,
            "average_rating": float(resource.average_rating),
            "bookmarks": resource.bookmarks.count(),
            "favorites": resource.favorites.count(),
            "comments": {"count": comments_total},
            "downloads": {"total": downloads_total},
            "ratings": {
                "count": ratings_total,
                "average": float(ratings_average or 0),
            },
            "event_counts": event_counts,
            "created_at": resource.created_at.isoformat() if resource.created_at else None,
        }

    @staticmethod
    def get_popular_content_trends(days: int = 7) -> dict:
        """Return trending content insights for dashboard widgets."""
        from apps.analytics.models import AnalyticsEvent
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)
        trending_resources = list(
            Resource.objects.filter(created_at__gte=since)
            .order_by("-download_count", "-view_count", "-created_at")
            .values("id", "title", "resource_type", "download_count", "view_count")[:10]
        )
        event_breakdown = list(
            AnalyticsEvent.objects.filter(timestamp__gte=since)
            .values("event_type")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        downloads = [
            {
                "date": row["day"].date().isoformat() if row["day"] else None,
                "count": row["count"],
            }
            for row in Download.objects.filter(created_at__gte=since, resource__isnull=False)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        ]
        new_resources = [
            {
                "date": row["day"].date().isoformat() if row["day"] else None,
                "count": row["count"],
            }
            for row in Resource.objects.filter(created_at__gte=since)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        ]

        return {
            "days": days,
            "resources": trending_resources,
            "events": event_breakdown,
            # Legacy keys expected by older tests/clients.
            "downloads": downloads,
            "new_resources": new_resources,
        }

    @staticmethod
    def get_top_contributors(limit: int = 10) -> List[dict]:
        """Return the top upload contributors as plain dictionaries."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        contributors = (
            User.objects.filter(is_active=True)
            .annotate(
                upload_count=Count("uploads", filter=Q(uploads__is_deleted=False), distinct=True),
                download_impact=Sum("uploads__download_count"),
            )
            .filter(upload_count__gt=0)
            .order_by("-upload_count", "-download_impact", "email")[:limit]
        )

        return [
            {
                "user_id": user.id,
                "email": user.email,
                "name": user.get_full_name() if hasattr(user, "get_full_name") else user.email,
                "upload_count": user.upload_count,
                "download_impact": user.download_impact or 0,
            }
            for user in contributors
        ]

    @staticmethod
    def get_most_downloaded_resources(limit: int = 10):
        """Return most downloaded resources as a queryset for serialization."""
        from apps.resources.models import Resource

        return (
            Resource.objects.select_related("uploaded_by", "course", "unit")
            .annotate(actual_downloads=Count("downloads", distinct=True))
            .order_by("-actual_downloads", "-download_count", "-view_count", "-created_at")[:limit]
        )

    @staticmethod
    def get_most_active_uploaders(limit: int = 10):
        """Return the most active uploaders as a queryset for serialization."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return (
            User.objects.filter(is_active=True)
            .annotate(
                upload_count=Count("uploads", filter=Q(uploads__is_deleted=False), distinct=True),
                total_downloads=Sum("uploads__download_count"),
            )
            .filter(upload_count__gt=0)
            .order_by("-upload_count", "-total_downloads", "email")[:limit]
        )

    @staticmethod
    def get_resources_by_course():
        """Group resources by course for dashboard charts."""
        from apps.resources.models import Resource

        return (
            Resource.objects.exclude(course__isnull=True)
            .values("course__id", "course__name", "course__code")
            .annotate(count=Count("id"))
            .order_by("-count", "course__name")
        )

    @staticmethod
    def get_daily_upload_trends(days: int = 30):
        """Return upload counts grouped by day."""
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)
        return (
            Resource.objects.filter(created_at__gte=since)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

    @staticmethod
    def get_daily_download_trends(days: int = 30):
        """Return download counts grouped by day."""
        from apps.downloads.models import Download

        since = timezone.now() - timedelta(days=days)
        return (
            Download.objects.filter(created_at__gte=since, resource__isnull=False)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

    @staticmethod
    def get_admin_dashboard_stats() -> dict:
        """Proxy admin stats to the dedicated admin analytics service."""
        return AdminAnalyticsService.get_dashboard_summary()

    @staticmethod
    def create_daily_snapshot(target_date: date = None):
        """Create or update a daily snapshot using the DailyMetric model."""
        from django.contrib.auth import get_user_model
        from apps.analytics.models import DailyMetric
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        User = get_user_model()
        target_date = target_date or date.today()

        snapshot, _created = DailyMetric.objects.update_or_create(
            date=target_date,
            defaults={
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(last_login__date=target_date).count(),
                "new_signups": User.objects.filter(date_joined__date=target_date).count(),
                "total_resources": Resource.objects.count(),
                "new_resources": Resource.objects.filter(created_at__date=target_date).count(),
                "total_downloads": Download.objects.filter(
                    created_at__date=target_date,
                    resource__isnull=False,
                ).count(),
            },
        )
        return snapshot

    @staticmethod
    def generate_weekly_report(end_date: date = None) -> dict:
        """Generate a compact weekly report from daily snapshots."""
        from django.contrib.auth import get_user_model
        from apps.analytics.models import DailyMetric
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        User = get_user_model()
        report_end = end_date or date.today()
        report_start = report_end - timedelta(days=6)

        metrics = DailyMetric.objects.filter(
            date__gte=report_start,
            date__lte=report_end,
        )

        if metrics.exists():
            new_users = sum(item.new_signups for item in metrics)
            new_resources = sum(item.new_resources for item in metrics)
            total_downloads = sum(item.total_downloads for item in metrics)
        else:
            new_users = User.objects.filter(
                date_joined__date__gte=report_start,
                date_joined__date__lte=report_end,
            ).count()
            new_resources = Resource.objects.filter(
                created_at__date__gte=report_start,
                created_at__date__lte=report_end,
            ).count()
            total_downloads = Download.objects.filter(
                created_at__date__gte=report_start,
                created_at__date__lte=report_end,
                resource__isnull=False,
            ).count()

        return {
            "period": {
                "start": report_start.isoformat(),
                "end": report_end.isoformat(),
            },
            "new_users": new_users,
            "new_resources": new_resources,
            "total_downloads": total_downloads,
        }


class MetricsAggregationService:
    """Service for aggregating daily metrics."""

    @staticmethod
    def aggregate_daily_metrics(target_date: date = None):
        """Aggregate metrics for a specific date."""
        from apps.analytics.models import AnalyticsEvent, DailyMetric
        from django.contrib.auth import get_user_model
        from apps.resources.models import Resource
        from apps.downloads.models import Download
        from apps.bookmarks.models import Bookmark
        from apps.favorites.models import Favorite
        from apps.comments.models import Comment
        from apps.ratings.models import Rating

        User = get_user_model()

        if not target_date:
            target_date = date.today() - timedelta(days=1)

        start_datetime = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)

        # Get metrics
        metrics = {
            'date': target_date,
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(last_login__gte=start_datetime).count(),
            'new_signups': User.objects.filter(date_joined__gte=start_datetime, date_joined__lt=end_datetime).count(),
            'total_resources': Resource.objects.count(),
            'new_resources': Resource.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
            'total_downloads': Download.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
            'total_bookmarks': Bookmark.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
            'total_favorites': Favorite.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
            'total_comments': Comment.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
            'total_ratings': Rating.objects.filter(created_at__gte=start_datetime, created_at__lt=end_datetime).count(),
        }

        # Calculate MAU/WAU/DAU
        dau = metrics['active_users']
        wau_start = target_date - timedelta(days=7)
        wau = User.objects.filter(last_login__gte=timezone.make_aware(timezone.datetime.combine(wau_start, timezone.datetime.min.time()))).count()
        mau_start = target_date - relativedelta(months=1)
        mau = User.objects.filter(last_login__gte=timezone.make_aware(timezone.datetime.combine(mau_start, timezone.datetime.min.time()))).count()

        metrics.update({
            'active_dau': dau,
            'active_wau': wau,
            'active_mau': mau,
        })

        # Save or update
        daily_metric, created = DailyMetric.objects.update_or_create(
            date=target_date,
            defaults=metrics
        )

        logger.info(f"Aggregated metrics for {target_date}")
        return daily_metric


class CohortAnalysisService:
    """Service for cohort analysis and retention tracking."""

    @staticmethod
    def calculate_cohort_retention(cohort_type: str = 'signup', months: int = 12):
        """Calculate retention rates for cohorts."""
        from apps.analytics.models import Cohort
        from django.contrib.auth import get_user_model
        from django.db.models.functions import TruncMonth

        User = get_user_model()

        # Get users grouped by signup month
        users_by_month = User.objects.annotate(
            cohort_month=TruncMonth('date_joined')
        ).values('cohort_month').annotate(count=Count('id'))

        for user_group in users_by_month:
            cohort_date = user_group['cohort_month'].date() if user_group['cohort_month'] else None
            if not cohort_date:
                continue

            # Check retention at each month
            retention = {}
            initial_count = user_group['count']

            for month_offset in range(months + 1):
                check_date = cohort_date + relativedelta(months=month_offset)
                
                # Count users who were active in this month
                active_count = User.objects.filter(
                    date_joined__lte=check_date,
                    last_login__gte=timezone.make_aware(timezone.datetime.combine(check_date, timezone.datetime.min.time()))
                ).count()

                if initial_count > 0:
                    retention[month_offset] = round((active_count / initial_count) * 100, 2)
                else:
                    retention[month_offset] = 0

            # Save cohort data
            Cohort.objects.update_or_create(
                cohort_date=cohort_date,
                cohort_type=cohort_type,
                defaults={
                    'retention_data': retention,
                    'initial_users': initial_count,
                    'total_retained': active_count,
                    'retention_rate': retention.get(6, 0),  # 6-month retention as summary
                }
            )

        logger.info(f"Calculated {cohort_type} cohort retention")
        return True

    @staticmethod
    def get_retention_report(cohort_type: str = 'signup') -> dict:
        """Get retention report for cohorts."""
        from apps.analytics.models import Cohort

        cohorts = Cohort.objects.filter(cohort_type=cohort_type).order_by('-cohort_date')[:12]

        return {
            'cohorts': [{
                'date': c.cohort_date.isoformat(),
                'initial_users': c.initial_users,
                'retention': c.retention_data,
                'rate_30d': c.retention_data.get(1, 0),
                'rate_90d': c.retention_data.get(3, 0),
                'rate_180d': c.retention_data.get(6, 0),
            } for c in cohorts]
        }


class LearningInsightsService:
    """Service for generating AI-powered learning insights."""

    @staticmethod
    def generate_insights_for_user(user):
        """Generate learning insights for a user."""
        from apps.analytics.models import LearningInsight
        from apps.analytics.services import AnalyticsService

        insights = []

        # Get recent activity
        timeline = AnalyticsService.get_user_activity_timeline(user, days=30)
        
        # Check for engagement drop
        if len(timeline) < 5:
            insight = LearningInsight.objects.create(
                user=user,
                insight_type='engagement_drop',
                title='Your activity has decreased',
                description='We noticed you haven\'t been as active recently. Keep up your study routine!',
                priority='medium',
                action_url='/resources/',
                action_text='Browse Resources'
            )
            insights.append(insight)

        # Check for resource gaps (user's course but no downloads)
        if hasattr(user, 'course') and user.course:
            from apps.resources.models import Resource
            
            # Find resources in user's course they haven't downloaded
            downloaded = user.downloads.values_list('resource_id', flat=True)
            course_resources = Resource.objects.filter(
                course=user.course,
                status='approved'
            ).exclude(id__in=downloaded)[:5]

            if course_resources.exists():
                insight = LearningInsight.objects.create(
                    user=user,
                    insight_type='resource_gap',
                    title='Explore more course materials',
                    description=f'There are {course_resources.count()} resources in your course you haven\'t seen yet.',
                    course_id=user.course.id,
                    priority='low',
                    action_url=f'/resources/?course={user.course.id}',
                    action_text='View Resources'
                )
                insights.append(insight)

        # Check study streak
        from apps.analytics.models import UserActivitySummary
        recent_activity = UserActivitySummary.objects.filter(
            user=user,
            period_type='daily'
        ).order_by('-period_start').first()

        if recent_activity and recent_activity.current_streak_days >= 7:
            insight = LearningInsight.objects.create(
                user=user,
                insight_type='progress',
                title=f'Great job! {recent_activity.current_streak_days} day streak',
                description='You\'re building a great study habit. Keep it up!',
                priority='low',
            )
            insights.append(insight)

        return insights

    @staticmethod
    def get_user_insights(user, unread_only: bool = False):
        """Get user's learning insights."""
        from apps.analytics.models import LearningInsight

        query = LearningInsight.objects.filter(user=user)
        
        if unread_only:
            query = query.filter(is_read=False)

        return query.order_by('-priority', '-created_at')

    @staticmethod
    def mark_insight_read(insight_id: int, user):
        """Mark an insight as read."""
        from apps.analytics.models import LearningInsight

        try:
            insight = LearningInsight.objects.get(id=insight_id, user=user)
            insight.is_read = True
            insight.read_at = timezone.now()
            insight.save()
            return True
        except LearningInsight.DoesNotExist:
            return False


class DashboardChartService:
    """Chart-focused helpers used by analytics views."""

    @staticmethod
    def get_user_activity_heatmap(user, days: int = 30) -> dict:
        """Return day/hour activity buckets for a user's recent activity."""
        from apps.activity.models import RecentActivity
        from apps.analytics.models import AnalyticsEvent

        since = timezone.now() - timedelta(days=days)
        event_heatmap = list(
            AnalyticsEvent.objects.filter(user=user, timestamp__gte=since)
            .annotate(day=TruncDay("timestamp"), hour=ExtractHour("timestamp"))
            .values("day", "hour")
            .annotate(count=Count("id"))
            .order_by("day", "hour")
        )
        if event_heatmap:
            buckets = [
                {
                    "date": row["day"].date().isoformat() if row["day"] else None,
                    "hour": int(row["hour"]) if row["hour"] is not None else None,
                    "count": row["count"],
                }
                for row in event_heatmap
            ]
            return {
                "labels": [
                    (
                        f"{entry['date']} {entry['hour']:02d}:00"
                        if entry["hour"] is not None and entry["date"]
                        else entry["date"]
                    )
                    for entry in buckets
                ],
                "values": [entry["count"] for entry in buckets],
                "buckets": buckets,
            }

        activity_heatmap = (
            RecentActivity.objects.filter(user=user, created_at__gte=since)
            .annotate(day=TruncDay("created_at"), hour=ExtractHour("created_at"))
            .values("day", "hour")
            .annotate(count=Count("id"))
            .order_by("day", "hour")
        )
        buckets = [
            {
                "date": row["day"].date().isoformat() if row["day"] else None,
                "hour": int(row["hour"]) if row["hour"] is not None else None,
                "count": row["count"],
            }
            for row in activity_heatmap
        ]
        return {
            "labels": [
                (
                    f"{entry['date']} {entry['hour']:02d}:00"
                    if entry["hour"] is not None and entry["date"]
                    else entry["date"]
                )
                for entry in buckets
            ],
            "values": [entry["count"] for entry in buckets],
            "buckets": buckets,
        }

    @staticmethod
    def get_downloads_chart_data(days: int = 30) -> dict:
        """Return download totals grouped by day for dashboard charts."""
        from apps.downloads.models import Download

        since = timezone.now() - timedelta(days=days)
        queryset = (
            Download.objects.filter(created_at__gte=since, resource__isnull=False)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        points = [
            {
                "date": row["day"].date().isoformat() if row["day"] else None,
                "count": row["count"],
            }
            for row in queryset
        ]
        return {
            "labels": [row["date"] for row in points],
            "values": [row["count"] for row in points],
            "points": points,
        }

    @staticmethod
    def get_resource_types_chart_data() -> dict:
        """Return the resource type distribution for charts."""
        from apps.resources.models import Resource

        queryset = (
            Resource.objects.values("resource_type")
            .annotate(count=Count("id"))
            .order_by("-count", "resource_type")
        )
        points = [
            {"resource_type": row["resource_type"], "count": row["count"]}
            for row in queryset
        ]
        return {
            "labels": [row["resource_type"] for row in points],
            "values": [row["count"] for row in points],
            "points": points,
        }


class AdminAnalyticsService:
    """Service for admin dashboard analytics."""

    @staticmethod
    def get_dashboard_summary() -> dict:
        """Get summary stats for admin dashboard."""
        from apps.analytics.models import DailyMetric, AnalyticsEvent
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        User = get_user_model()

        # Get today's metrics
        today = date.today()
        metrics = DailyMetric.objects.filter(date=today).first()

        # Get previous day for comparison
        prev_day = DailyMetric.objects.filter(date=today - timedelta(days=1)).first()

        # Get event counts for today
        today_start = timezone.now().replace(hour=0, minute=0, second=0)
        
        events_today = AnalyticsEvent.objects.filter(timestamp__gte=today_start).count()
        
        # Top events
        top_events = AnalyticsEvent.objects.filter(
            timestamp__gte=today_start - timedelta(days=7)
        ).values('event_type').annotate(count=Count('id')).order_by('-count')[:10]

        # Growth rates
        user_growth = 0
        if metrics and prev_day and prev_day.total_users > 0:
            user_growth = ((metrics.total_users - prev_day.total_users) / prev_day.total_users) * 100

        return {
            'total_users': metrics.total_users if metrics else User.objects.count(),
            'active_users': metrics.active_users if metrics else 0,
            'user_growth': round(user_growth, 2),
            'total_resources': metrics.total_resources if metrics else 0,
            'new_resources_today': metrics.new_resources if metrics else 0,
            'total_downloads_today': metrics.total_downloads if metrics else 0,
            'events_today': events_today,
            'top_events': list(top_events),
        }

    @staticmethod
    def get_realtime_stats() -> dict:
        """Get real-time platform stats."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta

        User = get_user_model()

        # Active users in last 5 minutes
        recent = timezone.now() - timedelta(minutes=5)
        active_now = User.objects.filter(last_login__gte=recent).count()

        # New signups today
        today_start = timezone.now().replace(hour=0, minute=0, second=0)
        new_signups_today = User.objects.filter(date_joined__gte=today_start).count()

        return {
            'active_users_now': active_now,
            'new_signups_today': new_signups_today,
            'timestamp': timezone.now().isoformat(),
        }
