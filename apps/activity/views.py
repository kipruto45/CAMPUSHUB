"""
Views for activity app.
"""

from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination

from .models import RecentActivity
from .serializers import (ActivityStatsSerializer, RecentActivitySerializer,
                          RecentFilesSerializer, RecentResourcesSerializer)
from .services import ActivityService


class RecentActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing recent activities."""

    serializer_class = RecentActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return RecentActivity.objects.filter(user=self.request.user).select_related(
            "resource", "personal_file", "bookmark", "bookmark__resource"
        )

    def get_serializer_class(self):
        if (
            self.action == "list"
            and self.request.query_params.get("format") == "resources"
        ):
            return RecentResourcesSerializer
        return RecentActivitySerializer


class RecentResourcesView(generics.ListAPIView):
    """View for recently viewed resources."""

    serializer_class = RecentResourcesSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return ActivityService.get_recent_resources(self.request.user, limit=20)


class RecentFilesView(generics.ListAPIView):
    """View for recently opened personal files."""

    serializer_class = RecentFilesSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return ActivityService.get_recent_personal_files(self.request.user, limit=20)


class RecentDownloadsView(generics.ListAPIView):
    """View for recently downloaded items."""

    serializer_class = RecentActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return ActivityService.get_recent_downloads(self.request.user, limit=20)


class RecentBookmarksView(generics.ListAPIView):
    """View for recently bookmarked items."""

    serializer_class = RecentActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return RecentActivity.objects.filter(
            user=self.request.user, activity_type="bookmarked_resource"
        ).select_related("bookmark", "bookmark__resource")[:20]


class UnifiedRecentActivityView(generics.ListAPIView):
    """
    Unified view for all recent activity.
    Combines views, downloads, and personal file opens.
    """

    serializer_class = RecentActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecentActivity.objects.none()
        return ActivityService.get_recent_activities(self.request.user, limit=20)


class ActivityStatsView(generics.RetrieveAPIView):
    """View for activity statistics."""

    permission_classes = [IsAuthenticated]
    serializer_class = ActivityStatsSerializer

    def retrieve(self, request, *args, **kwargs):
        stats = ActivityService.get_activity_stats(request.user)
        serializer = self.get_serializer(stats)
        return Response(serializer.data)


class ClearOldActivitiesView(generics.DestroyAPIView):
    """View for clearing old activities."""

    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        days = int(request.query_params.get("days", 90))
        deleted_count = ActivityService.clear_old_activities(request.user, days)
        return Response(
            {
                "message": f"Cleared {deleted_count} old activities",
                "deleted_count": deleted_count,
            }
        )
