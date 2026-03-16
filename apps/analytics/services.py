"""
Enhanced Analytics Services for CampusHub.
"""

import logging
from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger("analytics_logger")


class AnalyticsService:
    """
    Service for generating analytics and insights.
    """

    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_user_activity_summary(user, days=30):
        """
        Get activity summary for a user.
        """
        from apps.activity.models import RecentActivity
        from apps.bookmarks.models import Bookmark
        from apps.comments.models import Comment
        from apps.downloads.models import Download
        from apps.favorites.models import Favorite
        from apps.ratings.models import Rating
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)

        return {
            "uploads": Resource.objects.filter(uploaded_by=user).count(),
            "downloads": Download.objects.filter(user=user).count(),
            "bookmarks": Bookmark.objects.filter(user=user).count(),
            "favorites": Favorite.objects.filter(user=user).count(),
            "comments": Comment.objects.filter(user=user).count(),
            "ratings": Rating.objects.filter(user=user).count(),
            "recent_activities": RecentActivity.objects.filter(
                user=user, created_at__gte=since
            ).count(),
        }

    @staticmethod
    def get_user_engagement_score(user):
        """
        Calculate user engagement score (0-100).
        """
        from apps.activity.models import RecentActivity
        from apps.bookmarks.models import Bookmark
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        # Various engagement factors
        upload_count = Resource.objects.filter(uploaded_by=user).count()
        download_count = Download.objects.filter(user=user).count()
        bookmark_count = Bookmark.objects.filter(user=user).count()
        activity_count = RecentActivity.objects.filter(user=user).count()

        # Calculate score (weighted)
        score = (
            min(upload_count * 5, 25)  # Max 25 points
            + min(download_count * 0.5, 25)  # Max 25 points
            + min(bookmark_count * 1, 25)  # Max 25 points
            + min(activity_count * 0.5, 25)  # Max 25 points
        )

        return min(score, 100)

    @staticmethod
    def get_popular_content_trends(days=7):
        """
        Get content trends over time.
        """
        from django.db.models.functions import TruncDate

        from apps.downloads.models import Download
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)

        # Downloads per day
        downloads_per_day = (
            Download.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Resources created per day
        resources_per_day = (
            Resource.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return {
            "downloads": list(downloads_per_day),
            "new_resources": list(resources_per_day),
        }

    @staticmethod
    def get_user_demographics():
        """
        Get user demographics breakdown.
        """
        from apps.accounts.models import User

        # Users by faculty
        by_faculty = (
            User.objects.exclude(faculty__isnull=True)
            .values("faculty__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Users by course
        by_course = (
            User.objects.exclude(course__isnull=True)
            .values("course__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Users by year
        by_year = (
            User.objects.exclude(year_of_study__isnull=True)
            .values("year_of_study")
            .annotate(count=Count("id"))
            .order_by("year_of_study")
        )

        return {
            "by_faculty": list(by_faculty),
            "by_course": list(by_course),
            "by_year": list(by_year),
        }

    @staticmethod
    def get_resource_analytics(resource_id):
        """
        Get detailed analytics for a specific resource.
        """
        from apps.comments.models import Comment
        from apps.downloads.models import Download
        from apps.ratings.models import Rating
        from apps.resources.models import Resource

        try:
            resource = Resource.objects.get(pk=resource_id)
        except (Resource.DoesNotExist, ValidationError, ValueError, TypeError):
            return None

        # Download stats
        downloads = Download.objects.filter(resource=resource)
        total_downloads = downloads.count()

        # Rating stats
        ratings = Rating.objects.filter(resource=resource)
        avg_rating = ratings.aggregate(Avg("value"))["value__avg"] or 0
        rating_count = ratings.count()

        # Comment stats
        comment_count = Comment.objects.filter(resource=resource).count()

        # Download timeline
        downloads_timeline = (
            downloads.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("-date")[:30]
        )

        return {
            "resource": {
                "id": resource.id,
                "title": resource.title,
                "status": resource.status,
            },
            "downloads": {
                "total": total_downloads,
                "timeline": list(downloads_timeline),
            },
            "ratings": {
                "average": round(avg_rating, 2),
                "count": rating_count,
            },
            "comments": {
                "count": comment_count,
            },
        }

    @staticmethod
    def get_platform_health():
        """
        Get platform health metrics.
        """
        from apps.accounts.models import User
        from apps.downloads.models import Download
        from apps.notifications.models import Notification
        from apps.resources.models import Resource

        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        return {
            "users": {
                "total": User.objects.count(),
                "active_last_hour": User.objects.filter(
                    last_login__gte=hour_ago
                ).count(),
                "active_last_day": User.objects.filter(
                    last_login__gte=day_ago
                ).count(),
                "active_last_week": User.objects.filter(
                    last_login__gte=week_ago
                ).count(),
            },
            "resources": {
                "total": Resource.objects.count(),
                "approved": Resource.objects.filter(status="approved").count(),
                "pending": Resource.objects.filter(status="pending").count(),
            },
            "activity": {
                "downloads_today": Download.objects.filter(
                    created_at__gte=day_ago
                ).count(),
                "notifications_sent_today": Notification.objects.filter(
                    created_at__gte=day_ago
                ).count(),
            },
        }

    @staticmethod
    def get_top_contributors(limit=10):
        """
        Get top contributors (users who upload the most).
        """
        from apps.resources.models import Resource

        return (
            Resource.objects.filter(status="approved")
            .values(
                "uploaded_by__id",
                "uploaded_by__full_name",
                "uploaded_by__email",
            )
            .annotate(
                resource_count=Count("id"),
                total_downloads=Count("downloads"),
            )
            .order_by("-resource_count")[:limit]
        )

    @staticmethod
    def create_daily_snapshot():
        """
        Create a daily analytics snapshot for reporting.
        """
        from apps.analytics.models import DailyAnalytics

        today = timezone.now().date()

        # Check if snapshot already exists
        if DailyAnalytics.objects.filter(date=today).exists():
            logger.info(f"Daily snapshot for {today} already exists")
            return

        # Create snapshot
        snapshot = AnalyticsService.get_platform_health()

        DailyAnalytics.objects.create(
            date=today,
            total_users=snapshot["users"]["total"],
            active_users=snapshot["users"]["active_last_day"],
            total_resources=snapshot["resources"]["total"],
            approved_resources=snapshot["resources"]["approved"],
            pending_resources=snapshot["resources"]["pending"],
            total_downloads=snapshot["activity"]["downloads_today"],
        )

        logger.info(f"Created daily snapshot for {today}")

    @staticmethod
    def generate_weekly_report():
        """
        Generate weekly analytics report.
        """
        from apps.accounts.models import User
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        # Get weekly stats
        new_users = User.objects.filter(date_joined__gte=week_ago).count()
        new_resources = Resource.objects.filter(
            created_at__gte=week_ago
        ).count()
        downloads = Download.objects.filter(created_at__gte=week_ago).count()

        report = {
            "period": f"{week_ago.date()} to {now.date()}",
            "new_users": new_users,
            "new_resources": new_resources,
            "total_downloads": downloads,
        }

        logger.info(f"Weekly Report: {report}")
        return report

    @staticmethod
    def get_dashboard_stats():
        """Get high-level dashboard metrics."""
        from apps.accounts.models import User
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=30)

        return {
            "users": {
                "total": User.objects.count(),
                "new_last_30_days": User.objects.filter(
                    date_joined__gte=since
                ).count(),
            },
            "resources": {
                "total": Resource.objects.count(),
                "approved": Resource.objects.filter(status="approved").count(),
                "pending": Resource.objects.filter(status="pending").count(),
                "new_last_30_days": Resource.objects.filter(
                    created_at__gte=since
                ).count(),
            },
            "downloads": {
                "total": Download.objects.count(),
                "last_30_days": Download.objects.filter(
                    created_at__gte=since
                ).count(),
            },
        }

    @staticmethod
    def _resolve_dashboard_period(period):
        normalized = str(period or "month").strip().lower()
        if normalized == "week":
            return {"period": "week", "days": 7, "bucket": "day"}
        if normalized == "year":
            return {"period": "year", "days": 365, "bucket": "month"}
        return {"period": "month", "days": 30, "bucket": "week"}

    @staticmethod
    def _get_bucket_expression(field_name, bucket):
        if bucket == "day":
            return TruncDate(field_name)
        if bucket == "month":
            return TruncMonth(field_name)
        return TruncWeek(field_name)

    @staticmethod
    def _format_period_label(value, bucket):
        if value is None:
            return ""
        if bucket == "day":
            return value.strftime("%a")
        if bucket == "month":
            return value.strftime("%b")
        return value.strftime("%d %b")

    @staticmethod
    def _get_trend_counts(model, date_field, since, bucket, filters=None):
        filters = filters or {}
        queryset = (
            model.objects.filter(**{f"{date_field}__gte": since}, **filters)
            .annotate(period=AnalyticsService._get_bucket_expression(date_field, bucket))
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )
        return {item["period"]: int(item["count"] or 0) for item in queryset}

    @staticmethod
    def get_admin_dashboard_payload(period="month", top_limit=10):
        """Return analytics payload shaped for the admin analytics screen."""
        from apps.accounts.models import User
        from apps.downloads.models import Download
        from apps.resources.models import Resource, ResourceFile

        base_stats = AnalyticsService.get_dashboard_stats()
        period_config = AnalyticsService._resolve_dashboard_period(period)
        since = timezone.now() - timedelta(days=period_config["days"])
        bucket = period_config["bucket"]

        user_trends = AnalyticsService._get_trend_counts(
            User, "date_joined", since, bucket
        )
        resource_trends = AnalyticsService._get_trend_counts(
            Resource, "created_at", since, bucket
        )
        download_trends = AnalyticsService._get_trend_counts(
            Download,
            "created_at",
            since,
            bucket,
            filters={"resource__isnull": False},
        )

        periods = sorted(
            set(user_trends.keys())
            | set(resource_trends.keys())
            | set(download_trends.keys())
        )
        trends = [
            {
                "period": AnalyticsService._format_period_label(period_value, bucket),
                "users_count": user_trends.get(period_value, 0),
                "resources_count": resource_trends.get(period_value, 0),
                "downloads_count": download_trends.get(period_value, 0),
            }
            for period_value in periods
        ]

        top_resources = [
            {
                "id": str(resource.id),
                "title": resource.title,
                "download_count": int(
                    getattr(resource, "total_downloads", None)
                    or resource.download_count
                    or 0
                ),
                "view_count": int(resource.view_count or 0),
            }
            for resource in AnalyticsService.get_most_downloaded_resources(top_limit)
        ]

        top_users = [
            {
                "id": str(item["uploaded_by__id"] or ""),
                "name": item["uploaded_by__full_name"] or "Unknown",
                "email": item["uploaded_by__email"] or "",
                "upload_count": int(item["resource_count"] or 0),
            }
            for item in AnalyticsService.get_top_contributors(top_limit)
        ]

        resource_type_rows = list(
            Resource.objects.filter(status="approved")
            .values("resource_type")
            .annotate(count=Count("id"))
            .order_by("-count", "resource_type")[:10]
        )
        total_resource_types = sum(int(item["count"] or 0) for item in resource_type_rows)
        resource_types = [
            {
                "type": item["resource_type"] or "other",
                "count": int(item["count"] or 0),
                "percentage": (
                    round((int(item["count"] or 0) / total_resource_types) * 100, 1)
                    if total_resource_types
                    else 0.0
                ),
            }
            for item in resource_type_rows
        ]

        storage_used = int(
            (Resource.objects.aggregate(total=Sum("file_size")).get("total") or 0)
            + (ResourceFile.objects.aggregate(total=Sum("file_size")).get("total") or 0)
        )

        overview = {
            "total_users": int(base_stats["users"]["total"] or 0),
            "total_resources": int(base_stats["resources"]["total"] or 0),
            "total_downloads": int(
                Download.objects.filter(
                    created_at__gte=since,
                    resource__isnull=False,
                ).count()
            ),
            "total_uploads": int(
                Resource.objects.filter(created_at__gte=since).count()
            ),
            "active_users": int(User.objects.filter(last_login__gte=since).count()),
            "storage_used": storage_used,
        }

        return {
            **base_stats,
            "period": period_config["period"],
            "overview": overview,
            "trends": trends,
            "top_resources": top_resources,
            "top_users": top_users,
            "resource_types": resource_types,
        }

    @staticmethod
    def get_most_downloaded_resources(limit=10):
        """Return resources ranked by download count."""
        from apps.resources.models import Resource

        return (
            Resource.objects.filter(status="approved")
            .annotate(total_downloads=Count("downloads"))
            .order_by("-total_downloads", "-download_count", "-created_at")[
                :limit
            ]
        )

    @staticmethod
    def get_most_active_uploaders(limit=10):
        """Return users ranked by number of uploaded resources."""
        from apps.accounts.models import User

        return (
            User.objects.annotate(upload_count=Count("uploads"))
            .filter(upload_count__gt=0)
            .order_by("-upload_count", "-date_joined")[:limit]
        )

    @staticmethod
    def get_resources_by_course():
        """Return resource totals grouped by course."""
        from apps.resources.models import Resource

        return (
            Resource.objects.exclude(course__isnull=True)
            .values("course__id", "course__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    @staticmethod
    def get_daily_upload_trends(days=30):
        """Return daily upload counts."""
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)
        return (
            Resource.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

    @staticmethod
    def get_daily_download_trends(days=30):
        """Return daily download counts."""
        from apps.downloads.models import Download

        since = timezone.now() - timedelta(days=days)
        return (
            Download.objects.filter(
                created_at__gte=since,
                resource__isnull=False,
            )
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )


class DashboardChartService:
    """
    Service for generating chart data.
    """

    @staticmethod
    def get_downloads_chart_data(days=30):
        """Get downloads data for chart."""
        from django.db.models.functions import TruncDate

        from apps.downloads.models import Download

        since = timezone.now() - timedelta(days=days)

        data = (
            Download.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return {
            "labels": [item["date"].strftime("%Y-%m-%d") for item in data],
            "values": [item["count"] for item in data],
        }

    @staticmethod
    def get_resource_types_chart_data():
        """Get resource types distribution."""
        from apps.resources.models import Resource

        data = (
            Resource.objects.filter(status="approved")
            .values("file_type")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return {
            "labels": [item["file_type"] or "Unknown" for item in data],
            "values": [item["count"] for item in data],
        }

    @staticmethod
    def get_user_activity_heatmap(user, days=30):
        """Get user activity heatmap data."""
        from apps.activity.models import RecentActivity

        since = timezone.now() - timedelta(days=days)

        data = (
            RecentActivity.objects.filter(user=user, created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return {
            "labels": [item["date"].strftime("%Y-%m-%d") for item in data],
            "values": [item["count"] for item in data],
        }
