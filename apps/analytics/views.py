"""
Views for analytics app.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import models
from django.utils import timezone
from django.db.models.functions import TruncDay, ExtractHour
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import IsAdminOrModerator
from apps.resources.serializers import ResourceListSerializer

from .services import AnalyticsService, DashboardChartService
from .models import AnalyticsEvent
from apps.core.predictive_analytics import PredictiveAnalyticsService


def _safe_positive_int(value, default, minimum=1, maximum=365):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


class DashboardView(APIView):
    """Dashboard analytics view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
        period = request.query_params.get("period", "month")
        stats = AnalyticsService.get_admin_dashboard_payload(period=period)
        return Response(stats)


class UserActivitySummaryView(APIView):
    """Get user activity summary."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        score = AnalyticsService.get_user_engagement_score(request.user)
        return Response({"engagement_score": score})


class UserActivityHeatmapView(APIView):
    """Get user activity heatmap data."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        demographics = AnalyticsService.get_user_demographics()
        return Response(demographics)


class PlatformHealthView(APIView):
    """Get platform health metrics."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
        health = AnalyticsService.get_platform_health()
        return Response(health)


class ResourceAnalyticsView(APIView):
    """Get analytics for a specific resource."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        chart_data = DashboardChartService.get_resource_types_chart_data()
        return Response(chart_data)


class MostDownloadedResourcesView(APIView):
    """Most downloaded resources view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        data = AnalyticsService.get_resources_by_course()
        return Response(list(data))


class UploadTrendsView(APIView):
    """Upload trends view."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
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

    def get(self, request, *args, **kwargs):
        days = _safe_positive_int(
            request.query_params.get("days"),
            default=30,
            maximum=365,
        )
        data = AnalyticsService.get_daily_download_trends(days)
        return Response(list(data))


class AdminDashboardStatsView(APIView):
    """High-level admin dashboard stats."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
        stats = AnalyticsService.get_admin_dashboard_stats()
        return Response(stats)


class EventIngestView(APIView):
    """
    Lightweight event ingestion endpoint for client-side tracking.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        event_type = payload.get("event_type")
        event_name = payload.get("event_name") or event_type

        if not event_type:
            return Response({"error": "event_type is required"}, status=status.HTTP_400_BAD_REQUEST)

        event = AnalyticsEvent.objects.create(
            user=request.user if request.user and request.user.is_authenticated else None,
            session_id=payload.get("session_id", ""),
            event_type=event_type,
            event_name=event_name,
            resource_id=payload.get("resource_id"),
            course_id=payload.get("course_id"),
            unit_id=payload.get("unit_id"),
            properties=payload.get("properties", {}),
            referrer=payload.get("referrer", ""),
            utm_source=payload.get("utm_source", ""),
            utm_medium=payload.get("utm_medium", ""),
            utm_campaign=payload.get("utm_campaign", ""),
            device_type=payload.get("device_type", ""),
            browser=payload.get("browser", ""),
            os=payload.get("os", ""),
            country=payload.get("country", ""),
            city=payload.get("city", ""),
            duration_seconds=payload.get("duration_seconds"),
        )

        return Response({"id": str(event.id), "created": True}, status=status.HTTP_201_CREATED)


class EventAnalyticsView(APIView):
    """
    Event analytics for dashboards (attendance trend, type distribution, heatmap).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Event analytics",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "attendance_trend": {"type": "array"},
                    "type_distribution": {"type": "array"},
                    "heatmap": {"type": "array"},
                },
                "example": {
                    "attendance_trend": [{"period": "2026-03-01", "registered": 20, "attended": 15}],
                    "type_distribution": [{"type": "event_attended", "count": 10}],
                    "heatmap": [{"slot": "H10", "count": 5}],
                },
            }
        },
    )
    def get(self, request, *args, **kwargs):
        period = request.query_params.get("period", "month")
        days = 7 if period == "week" else 30 if period == "month" else 365
        since = timezone.now() - timezone.timedelta(days=days)

        qs = AnalyticsEvent.objects.filter(timestamp__gte=since)

        # Attendance trend approximation: split event types into registered/attended buckets
        agg = (
            qs.annotate(day=TruncDay("timestamp"))
            .values("day", "event_type")
            .annotate(count=models.Count("id"))
            .order_by("day")
        )
        day_map = {}
        for row in agg:
            key = row["day"].date().isoformat()
            bucket = day_map.setdefault(key, {"period": key, "registered": 0, "attended": 0})
            if row["event_type"] in {"event_attend", "event_attended", "attendance"}:
                bucket["attended"] += row["count"]
            else:
                bucket["registered"] += row["count"]
        attendance_trend = list(day_map.values())

        type_counts = (
            qs.values("event_type")
            .annotate(count=models.Count("id"))
            .order_by("-count")
        )
        type_distribution = [
            {"type": row["event_type"] or "unknown", "count": row["count"]}
            for row in type_counts
        ]

        heat_counts = (
            qs.annotate(hour=ExtractHour("timestamp"))
            .values("hour")
            .annotate(count=models.Count("id"))
            .order_by("hour")
        )
        heatmap = [{"slot": f"H{int(row['hour']):02d}", "count": row["count"]} for row in heat_counts]

        payload = {
            "attendance_trend": attendance_trend,
            "type_distribution": type_distribution,
            "demographics": [],
            "registration_vs_attendance": [],
            "popular_categories": [],
            "heatmap": heatmap,
        }
        return Response(payload)


# =========================================================================
# At-Risk Student Views
# =========================================================================


class AtRiskStudentsView(APIView):
    """
    Get list of at-risk students.
    """

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    @extend_schema(
        summary="At-risk students",
        parameters=[
            OpenApiParameter(
                name="risk_level",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by risk level (low, medium, high, critical)",
                enum=["low", "medium", "high", "critical"],
            ),
            OpenApiParameter(
                name="course_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by course ID",
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of results",
                default=50,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        risk_level = request.query_params.get("risk_level")
        course_id = request.query_params.get("course_id")
        limit = _safe_positive_int(request.query_params.get("limit"), default=50, maximum=100)

        at_risk_students = PredictiveAnalyticsService.get_at_risk_students(
            risk_level=risk_level,
            course_id=course_id,
            limit=limit
        )

        return Response({
            "count": len(at_risk_students),
            "students": at_risk_students
        })


class StudentRiskHistoryView(APIView):
    """
    Get risk assessment history for a student.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Student risk history",
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="User ID to get history for",
                required=True,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of records",
                default=30,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        try:
            user_id = int(user_id)
        except ValueError:
            return Response({"error": "Invalid user_id"}, status=400)

        limit = _safe_positive_int(request.query_params.get("limit"), default=30, maximum=100)

        history = PredictiveAnalyticsService.get_student_risk_history(user_id, limit)

        return Response({
            "user_id": user_id,
            "history": history
        })


class ManualRiskAssessmentView(APIView):
    """
    Manually trigger a risk assessment for a student.
    """

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    @extend_schema(
        summary="Manual risk assessment",
        request=inline_serializer(
            name="ManualRiskAssessmentRequest",
            fields={
                "user_id": serializers.IntegerField(help_text="User ID to assess"),
                "course_id": serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text="Optional course ID",
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name="ManualRiskAssessmentResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "assessment": serializers.DictField(required=False),
                },
            )
        },
    )
    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        course_id = request.data.get("course_id")

        result = PredictiveAnalyticsService.trigger_manual_assessment(user_id, course_id)

        if not result.get("success"):
            return Response(result, status=404)

        return Response(result)


class AtRiskSummaryView(APIView):
    """
    Get summary of at-risk students across the platform.
    """

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get(self, request, *args, **kwargs):
        summary = PredictiveAnalyticsService.get_at_risk_summary()
        return Response(summary)
