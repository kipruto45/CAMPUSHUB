"""
URL configuration for analytics app.
"""

from django.urls import path

from .views import (ContentTrendsView, DashboardView,
                    DownloadTrendsView, DownloadsChartView,
                    MostActiveUploadersView, MostDownloadedResourcesView,
                    PlatformHealthView, ResourceAnalyticsView,
                    ResourcesByCourseView, ResourceTypesChartView,
                    TopContributorsView, UploadTrendsView,
                    UserActivityHeatmapView, UserActivitySummaryView,
                    UserDemographicsView, UserEngagementScoreView,
                    AdminDashboardStatsView,
                    EventIngestView, EventAnalyticsView,
                    AtRiskStudentsView, StudentRiskHistoryView, ManualRiskAssessmentView,
                    AtRiskSummaryView)

app_name = "analytics"

urlpatterns = [
    # Event tracking (public endpoints for client-side analytics)
    path("track/", EventIngestView.as_view(), name="track-event"),
    path("ingest/", EventIngestView.as_view(), name="event-ingest"),
    
    # Dashboard
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path(
        "user/activity-summary/",
        UserActivitySummaryView.as_view(),
        name="user-activity-summary",
    ),
    path(
        "user/engagement-score/",
        UserEngagementScoreView.as_view(),
        name="user-engagement-score",
    ),
    path(
        "user/activity-heatmap/",
        UserActivityHeatmapView.as_view(),
        name="user-activity-heatmap",
    ),
    path("demographics/", UserDemographicsView.as_view(), name="demographics"),
    path("health/", PlatformHealthView.as_view(), name="health"),
    path(
        "resource-analytics/",
        ResourceAnalyticsView.as_view(),
        name="resource-analytics",
    ),
    path("content-trends/", ContentTrendsView.as_view(), name="content-trends"),
    path("contributors/", TopContributorsView.as_view(), name="contributors"),
    path("downloads-chart/", DownloadsChartView.as_view(), name="downloads-chart"),
    path(
        "resource-types-chart/",
        ResourceTypesChartView.as_view(),
        name="resource-types-chart",
    ),
    path("resources/", MostDownloadedResourcesView.as_view(), name="most-downloaded"),
    path(
        "uploaders/",
        MostActiveUploadersView.as_view(),
        name="most-active-uploaders",
    ),
    path(
        "resources-by-course/",
        ResourcesByCourseView.as_view(),
        name="resources-by-course",
    ),
    path("upload-trends/", UploadTrendsView.as_view(), name="upload-trends"),
    path("download-trends/", DownloadTrendsView.as_view(), name="download-trends"),
    path("events/", EventAnalyticsView.as_view(), name="event-analytics"),
    
    # Admin stats
    path("admin/stats/", AdminDashboardStatsView.as_view(), name="admin-stats"),
    
    # At-risk student endpoints
    path("at-risk/students/", AtRiskStudentsView.as_view(), name="at-risk-students"),
    path("at-risk/summary/", AtRiskSummaryView.as_view(), name="at-risk-summary"),
    path("at-risk/history/", StudentRiskHistoryView.as_view(), name="student-risk-history"),
    path("at-risk/assess/", ManualRiskAssessmentView.as_view(), name="manual-risk-assessment"),
]
