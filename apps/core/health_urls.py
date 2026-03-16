"""
URL configuration for health checks.
"""

from django.urls import path

from . import health

app_name = "health"

urlpatterns = [
    path("", health.health_check, name="health"),
    path("ready/", health.readiness_check, name="readiness"),
    path("maintenance/", health.maintenance_check, name="maintenance"),
]
