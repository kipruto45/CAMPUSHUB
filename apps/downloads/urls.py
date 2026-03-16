"""
URL configuration for downloads app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (DownloadHistoryViewSet, DownloadPersonalFileView,
                    DownloadResourceView, DownloadStatsView,
                    RecentDownloadsView, ResourceDownloadCountView,
                    UserDownloadCheckView)

app_name = "downloads"

router = DefaultRouter()
router.register(r"history", DownloadHistoryViewSet, basename="download-history")

urlpatterns = [
    # Public resource download
    path(
        "resources/<uuid:resource_id>/download/",
        DownloadResourceView.as_view(),
        name="download-resource",
    ),
    path(
        "resources/<uuid:resource_id>/count/",
        ResourceDownloadCountView.as_view(),
        name="resource-download-count",
    ),
    path(
        "resources/<uuid:resource_id>/check/",
        UserDownloadCheckView.as_view(),
        name="resource-download-check",
    ),
    # Personal file download
    path(
        "library/files/<uuid:file_id>/download/",
        DownloadPersonalFileView.as_view(),
        name="download-personal-file",
    ),
    # Recent downloads
    path("recent/", RecentDownloadsView.as_view(), name="recent-downloads"),
    # Download stats
    path("stats/", DownloadStatsView.as_view(), name="download-stats"),
    # Router URLs
    path("", include(router.urls)),
]
