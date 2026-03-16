"""
URL configuration for ratings app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RateResourceView, RatingViewSet, ResourceRatingListView

app_name = "ratings"

router = DefaultRouter()
router.register(r"ratings", RatingViewSet, basename="rating")

urlpatterns = [
    path(
        "resources/<uuid:resource_id>/ratings/",
        ResourceRatingListView.as_view(),
        name="resource-ratings",
    ),
    path(
        "resources/<uuid:resource_id>/rate/",
        RateResourceView.as_view(),
        name="rate-resource",
    ),
    path("", include(router.urls)),
]
