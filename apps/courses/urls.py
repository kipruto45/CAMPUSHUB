"""
URL configuration for courses app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.resources.views import (CourseProgressSummaryListView,
                                  CourseProgressSummaryUpdateView)
from .views import CourseListView, CourseViewSet, UnitListView, UnitViewSet

app_name = "courses"

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"units", UnitViewSet, basename="unit")

urlpatterns = [
    path("courses/public/", CourseListView.as_view(), name="course-public-list"),
    path("courses/progress/", CourseProgressSummaryListView.as_view(), name="course-progress-list"),
    path(
        "courses/<uuid:course_id>/progress/",
        CourseProgressSummaryUpdateView.as_view(),
        name="course-progress-detail",
    ),
    path("units/public/", UnitListView.as_view(), name="unit-public-list"),
    path("", include(router.urls)),
]
