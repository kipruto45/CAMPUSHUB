"""
URL configuration for the Dashboard API.
"""

from django.urls import path

from .views import (DashboardRecentActivityView, DashboardRecommendationsView,
                    DashboardStatsView, DashboardView)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("activity/", DashboardRecentActivityView.as_view(), name="dashboard-activity"),
    path(
        "recommendations/",
        DashboardRecommendationsView.as_view(),
        name="dashboard-recommendations",
    ),
]
