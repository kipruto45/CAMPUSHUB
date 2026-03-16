"""
URL configuration for resources app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (FolderViewSet, LibraryDashboardView, MyUploadsView,
                    PersonalFolderViewSet, PersonalResourceViewSet,
                    RelatedResourcesView, ResourceCreateView, ResourceListView,
                    ResourceUpdateView, ResourceViewSet, SaveToLibraryView,
                    SaveToPersonalLibraryView, CreateResourceRequestView,
                    ListResourceRequestsView, UpvoteResourceRequestView)

app_name = "resources"

router = DefaultRouter()
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"folders", FolderViewSet, basename="folder")
router.register(r"personal-folders", PersonalFolderViewSet, basename="personal-folder")
router.register(
    r"personal-resources", PersonalResourceViewSet, basename="personal-resource"
)

urlpatterns = [
    path(
        "resources/public/", ResourceListView.as_view(), name="approved-resource-list"
    ),
    path("resources/upload/", ResourceCreateView.as_view(), name="resource-upload"),
    path("resources/my-uploads/", MyUploadsView.as_view(), name="my-uploads"),
    path("resources/<uuid:pk>/", ResourceUpdateView.as_view(), name="resource-update"),
    path(
        "resources/<uuid:resource_id>/save/",
        SaveToLibraryView.as_view(),
        name="save-to-library",
    ),
    path(
        "resources/<uuid:resource_id>/save-personal/",
        SaveToPersonalLibraryView.as_view(),
        name="save-to-personal-library",
    ),
    path(
        "resources/<uuid:resource_id>/related/",
        RelatedResourcesView.as_view(),
        name="related-resources",
    ),
    # Personal Library Dashboard
    path("library/", LibraryDashboardView.as_view(), name="library-dashboard"),
    # Resource Requests
    path(
        "resource-requests/",
        CreateResourceRequestView.as_view(),
        name="create-resource-request"
    ),
    path(
        "resource-requests/list/",
        ListResourceRequestsView.as_view(),
        name="list-resource-requests"
    ),
    path(
        "resource-requests/<uuid:request_id>/upvote/",
        UpvoteResourceRequestView.as_view(),
        name="upvote-resource-request"
    ),
    path("", include(router.urls)),
]
