"""
Views for analytics app.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import IsAdminOrModerator
from apps.resources.serializers import ResourceListSerializer

from .services import AnalyticsService, DashboardChartService


def _safe_positive_int(value, default, minimum=1, maximum=365):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


class DashboardView(APIView):
    """Dashboard analytics view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        period = request.query_params.get("period", "month")
        stats = AnalyticsService.get_admin_dashboard_payload(period=period)
        return Response(stats)


class UserActivitySummaryView(APIView):
    """Get user activity summary."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        summary = AnalyticsService.get_user_activity_summary(request.user, days)
        return Response(summary)


class UserEngagementScoreView(APIView):
    """Get user engagement score."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        score = AnalyticsService.get_user_engagement_score(request.user)
        return Response({"engagement_score": score})


class UserActivityHeatmapView(APIView):
    """Get user activity heatmap data."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        heatmap = DashboardChartService.get_user_activity_heatmap(request.user, days)
        return Response(heatmap)


class UserDemographicsView(APIView):
    """Get user demographics (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        demographics = AnalyticsService.get_user_demographics()
        return Response(demographics)


class PlatformHealthView(APIView):
    """Get platform health metrics."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        health = AnalyticsService.get_platform_health()
        return Response(health)


class ResourceAnalyticsView(APIView):
    """Get analytics for a specific resource."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        resource_id = request.query_params.get("resource_id")
        if not resource_id:
            return Response({"error": "resource_id required"}, status=400)

        analytics = AnalyticsService.get_resource_analytics(resource_id)
        if not analytics:
            return Response({"error": "Resource not found"}, status=404)

        return Response(analytics)


class ContentTrendsView(APIView):
    """Get content trends over time."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=7,
            maximum=365,
        )
        trends = AnalyticsService.get_popular_content_trends(days)
        return Response(trends)


class TopContributorsView(APIView):
    """Get top contributors."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        limit = _safe_positive_int(
            request.query_params.get("limit"),
            default=10,
            maximum=100,
        )
        contributors = AnalyticsService.get_top_contributors(limit)
        return Response(list(contributors))


class DownloadsChartView(APIView):
    """Get downloads chart data."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        chart_data = DashboardChartService.get_downloads_chart_data(days)
        return Response(chart_data)


class ResourceTypesChartView(APIView):
    """Get resource types distribution chart."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        chart_data = DashboardChartService.get_resource_types_chart_data()
        return Response(chart_data)


class MostDownloadedResourcesView(APIView):
    """Most downloaded resources view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        limit = _safe_positive_int(
            request.query_params.get("limit"),
            default=10,
            maximum=100,
        )
        resources = AnalyticsService.get_most_downloaded_resources(limit)
        serializer = ResourceListSerializer(
            resources, many=True, context={"request": request}
        )
        return Response(serializer.data)


class MostActiveUploadersView(APIView):
    """Most active uploaders view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        limit = _safe_positive_int(
            request.query_params.get("limit"),
            default=10,
            maximum=100,
        )
        users = AnalyticsService.get_most_active_uploaders(limit)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class ResourcesByCourseView(APIView):
    """Resources by course view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        data = AnalyticsService.get_resources_by_course()
        return Response(list(data))


class UploadTrendsView(APIView):
    """Upload trends view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        data = AnalyticsService.get_daily_upload_trends(days)
        return Response(list(data))


class DownloadTrendsView(APIView):
    """Download trends view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        data = AnalyticsService.get_daily_download_trends(days)
        return Response(list(data))
