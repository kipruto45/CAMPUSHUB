"""
URL configuration for favorites app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (FavoriteCreateView, FavoriteStatsView, FavoriteToggleView,
                    FavoriteViewSet,
                    FolderFavoriteToggleView, PersonalFileFavoriteToggleView,
                    ResourceFavoriteToggleView)

app_name = "favorites"

router = DefaultRouter()
router.register(r"", FavoriteViewSet, basename="favorite")

urlpatterns = [
    # Backward-compatible aliases
    path("create/", FavoriteCreateView.as_view(), name="favorite-create"),
    path("toggle/", FavoriteToggleView.as_view(), name="favorite-toggle"),
    path("stats/", FavoriteStatsView.as_view(), name="favorite-stats"),
    # Resource favorite toggle
    path(
        "resources/<uuid:resource_id>/favorite/",
        ResourceFavoriteToggleView.as_view(),
        name="resource-favorite-toggle",
    ),
    # Personal file favorite toggle
    path(
        "library/files/<uuid:file_id>/favorite/",
        PersonalFileFavoriteToggleView.as_view(),
        name="file-favorite-toggle",
    ),
    # Folder favorite toggle
    path(
        "library/folders/<uuid:folder_id>/favorite/",
        FolderFavoriteToggleView.as_view(),
        name="folder-favorite-toggle",
    ),
    # REST style favorites endpoints:
    # GET /api/favorites/
    # POST /api/favorites/
    # DELETE /api/favorites/{id}/
    path("", include(router.urls)),
]
