"""
URL configuration for reports app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReportViewSet

app_name = "reports"

router = DefaultRouter()
router.register(r"reports", ReportViewSet, basename="report")

urlpatterns = [
    path("", include(router.urls)),
]
