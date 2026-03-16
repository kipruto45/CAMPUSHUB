"""
URL configuration for comments app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CommentViewSet, ResourceCommentListView

app_name = "comments"

router = DefaultRouter()
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path(
        "resources/<uuid:resource_id>/comments/",
        ResourceCommentListView.as_view(),
        name="resource-comments",
    ),
    path("", include(router.urls)),
]
