"""
URL configuration for announcements app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (AnnouncementAdminViewSet, AnnouncementViewSet,
                    DashboardAnnouncementsView)

app_name = "announcements"

router = DefaultRouter()
router.register(r"admin", AnnouncementAdminViewSet, basename="announcement-admin")

urlpatterns = [
    # Student-facing endpoints
    path(
        "",
        AnnouncementViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="announcement-list",
    ),
    path(
        "pinned/",
        AnnouncementViewSet.as_view(
            {
                "get": "pinned",
            }
        ),
        name="announcement-pinned",
    ),
    # Dashboard preview
    path(
        "dashboard/",
        DashboardAnnouncementsView.as_view(),
        name="dashboard-announcements",
    ),
    # Admin endpoints
    path("", include(router.urls)),
    path(
        "<slug:slug>/",
        AnnouncementViewSet.as_view(
            {
                "get": "retrieve",
            }
        ),
        name="announcement-detail",
    ),
]
