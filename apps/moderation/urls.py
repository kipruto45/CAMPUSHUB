"""
URL configuration for moderation app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (AdminActivityLogViewSet, ApproveResourceView,
                    ArchiveResourceView, FlagResourceView,
                    ModerationLogViewSet, PendingResourcesView,
                    RejectResourceView, RestoreResourceView)

app_name = "moderation"

router = DefaultRouter()
router.register(r"logs", ModerationLogViewSet, basename="moderation-log")
router.register(r"activity-logs", AdminActivityLogViewSet, basename="admin-activity-log")

urlpatterns = [
    path(
        "pending-resources/", PendingResourcesView.as_view(), name="pending-resources"
    ),
    path(
        "resources/<uuid:resource_id>/approve/",
        ApproveResourceView.as_view(),
        name="approve-resource",
    ),
    path(
        "resources/<uuid:resource_id>/reject/",
        RejectResourceView.as_view(),
        name="reject-resource",
    ),
    path(
        "resources/<uuid:resource_id>/flag/",
        FlagResourceView.as_view(),
        name="flag-resource",
    ),
    path(
        "resources/<uuid:resource_id>/archive/",
        ArchiveResourceView.as_view(),
        name="archive-resource",
    ),
    path(
        "resources/<uuid:resource_id>/restore/",
        RestoreResourceView.as_view(),
        name="restore-resource",
    ),
    path("", include(router.urls)),
]
