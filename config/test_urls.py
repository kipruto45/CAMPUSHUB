"""Minimal URL config for targeted test execution."""

from django.urls import include, path

urlpatterns = [
    path(
        "api/admin-management/",
        include(
            ("apps.admin_management.urls", "admin_management"),
            namespace="admin_management",
        ),
    ),
]
