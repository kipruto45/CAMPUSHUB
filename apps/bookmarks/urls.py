"""
URL configuration for bookmarks app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookmarkViewSet

app_name = "bookmarks"

router = DefaultRouter()
router.register(r"bookmarks", BookmarkViewSet, basename="bookmark")

urlpatterns = [
    path("", include(router.urls)),
]
