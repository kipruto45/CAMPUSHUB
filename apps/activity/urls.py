"""
URL configuration for activity app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (ActivityStatsView, ClearOldActivitiesView,
                    RecentActivityViewSet, RecentBookmarksView,
                    RecentDownloadsView, RecentFilesView, RecentResourcesView,
                    UnifiedRecentActivityView)

app_name = "activity"

router = DefaultRouter()
router.register(r"", RecentActivityViewSet, basename="activity")

urlpatterns = [
    # Unified recent activity
    path("recent/", UnifiedRecentActivityView.as_view(), name="unified-recent"),
    # Recent by type
    path("recent/resources/", RecentResourcesView.as_view(), name="recent-resources"),
    path("recent/files/", RecentFilesView.as_view(), name="recent-files"),
    path("recent/downloads/", RecentDownloadsView.as_view(), name="recent-downloads"),
    path("recent/bookmarks/", RecentBookmarksView.as_view(), name="recent-bookmarks"),
    # Activity statistics
    path("stats/", ActivityStatsView.as_view(), name="activity-stats"),
    # Clear old activities
    path("clear/", ClearOldActivitiesView.as_view(), name="clear-old"),
    # Router URLs
    path("", include(router.urls)),
]
