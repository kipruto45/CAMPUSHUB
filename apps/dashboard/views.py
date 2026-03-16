"""
Views for the Dashboard API.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import JWTAuthentication

from .serializers import (DashboardQuickStatsSerializer,
                          DashboardResponseSerializer)
from .services import DashboardQuickStatsService, DashboardService


class DashboardView(APIView):
    """
    API endpoint for user dashboard.

    GET /api/dashboard/

    Returns comprehensive dashboard data including:
    - User summary with profile completion
    - Quick statistics
    - Recent activity
    - Recommendations
    - Announcements
    - Pending uploads
    - Notification summary
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get dashboard data for the authenticated user.

        Returns:
            Response: Dashboard data including user summary, stats, etc.
        """
        service = DashboardService(request.user)
        data = service.get_dashboard_data()

        serializer = DashboardResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardStatsView(APIView):
    """
    API endpoint for quick dashboard stats.

    GET /api/dashboard/stats/

    Returns quick statistics for the authenticated user.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get quick stats for the authenticated user.

        Returns:
            Response: Quick statistics including bookmarks, uploads, downloads, storage.
        """
        service = DashboardQuickStatsService(request.user)
        data = service.get_stats()

        serializer = DashboardQuickStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardRecentActivityView(APIView):
    """
    API endpoint for recent activity.

    GET /api/dashboard/activity/

    Returns recent activity for the authenticated user.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get recent activity for the authenticated user.

        Returns:
            Response: Recent uploads, downloads, and bookmarks.
        """
        service = DashboardService(request.user)
        data = service._get_recent_activity()

        return Response(data, status=status.HTTP_200_OK)


class DashboardRecommendationsView(APIView):
    """
    API endpoint for recommendations.

    GET /api/dashboard/recommendations/

    Returns personalized recommendations for the authenticated user.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get recommendations for the authenticated user.

        Returns:
            Response: Trending, course-related, and recently added resources.
        """
        service = DashboardService(request.user)
        data = service._get_recommendations()

        return Response(data, status=status.HTTP_200_OK)
