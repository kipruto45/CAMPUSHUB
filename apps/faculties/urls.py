"""
URL configuration for faculties app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (DepartmentListView, DepartmentViewSet, FacultyListView,
                    FacultyViewSet, SeedCoursesView)

app_name = "faculties"

router = DefaultRouter()
router.register(r"faculties", FacultyViewSet, basename="faculty")
router.register(r"departments", DepartmentViewSet, basename="department")

urlpatterns = [
    path("faculties/public/", FacultyListView.as_view(), name="faculty-public-list"),
    path(
        "departments/public/",
        DepartmentListView.as_view(),
        name="department-public-list",
    ),
    path("seed-courses/", SeedCoursesView.as_view(), name="seed-courses"),
    path("", include(router.urls)),
]
