"""URL configuration for admin management module."""

from django.urls import path

from apps.admin_management import views
from apps.admin_management import backup

app_name = "admin_management"

urlpatterns = [
    path("dashboard/", views.AdminDashboardView.as_view(), name="dashboard"),
    path("stats/", views.AdminStatsView.as_view(), name="stats"),
    path("search/", views.AdminGlobalSearchView.as_view(), name="global-search"),
    path("system-health/", views.AdminSystemHealthView.as_view(), name="system-health"),
    path("users/", views.AdminUserListView.as_view(), name="user-list"),
    path(
        "users/<int:user_id>/", views.AdminUserDetailView.as_view(), name="user-detail"
    ),
    path(
        "users/<int:user_id>/activities/",
        views.AdminUserActivityListView.as_view(),
        name="user-activities",
    ),
    path(
        "users/<int:user_id>/status/",
        views.AdminUserStatusUpdateView.as_view(),
        name="user-status",
    ),
    path(
        "users/<int:user_id>/role/",
        views.AdminUserRoleUpdateView.as_view(),
        name="user-role",
    ),
    path("resources/", views.AdminResourceListView.as_view(), name="resource-list"),
    path(
        "resources/<uuid:resource_id>/",
        views.AdminResourceDetailView.as_view(),
        name="resource-detail",
    ),
    path(
        "resources/<uuid:resource_id>/approve/",
        views.AdminApproveResourceView.as_view(),
        name="resource-approve",
    ),
    path(
        "resources/<uuid:resource_id>/reject/",
        views.AdminRejectResourceView.as_view(),
        name="resource-reject",
    ),
    path(
        "resources/<uuid:resource_id>/pin/",
        views.AdminPinResourceView.as_view(),
        name="resource-pin",
    ),
    path(
        "resources/bulk-action/",
        views.AdminBulkResourceActionView.as_view(),
        name="resource-bulk-action",
    ),
    path("reports/", views.AdminReportListView.as_view(), name="report-list"),
    path(
        "reports/<uuid:report_id>/",
        views.AdminReportDetailView.as_view(),
        name="report-detail",
    ),
    path(
        "reports/<uuid:report_id>/resolve/",
        views.AdminResolveReportView.as_view(),
        name="report-resolve",
    ),
    path(
        "reports/<uuid:report_id>/dismiss/",
        views.AdminDismissReportView.as_view(),
        name="report-dismiss",
    ),
    path(
        "announcements/",
        views.AdminAnnouncementListView.as_view(),
        name="announcement-list",
    ),
    path(
        "announcements/<uuid:announcement_id>/",
        views.AdminAnnouncementDetailView.as_view(),
        name="announcement-detail",
    ),
    path(
        "announcements/<uuid:announcement_id>/publish/",
        views.AdminPublishAnnouncementView.as_view(),
        name="announcement-publish",
    ),
    path(
        "announcements/<uuid:announcement_id>/archive/",
        views.AdminArchiveAnnouncementView.as_view(),
        name="announcement-archive",
    ),
    path(
        "announcements/<uuid:announcement_id>/unpublish/",
        views.AdminUnpublishAnnouncementView.as_view(),
        name="announcement-unpublish",
    ),
    path("study-groups/", views.AdminStudyGroupListView.as_view(), name="study-group-list"),
    path(
        "study-groups/<uuid:group_id>/",
        views.AdminStudyGroupDetailView.as_view(),
        name="study-group-detail",
    ),
    path("faculties/", views.AdminFacultyListView.as_view(), name="faculty-list"),
    path(
        "faculties/<uuid:faculty_id>/",
        views.AdminFacultyDetailView.as_view(),
        name="faculty-detail",
    ),
    path(
        "departments/", views.AdminDepartmentListView.as_view(), name="department-list"
    ),
    path(
        "departments/<uuid:department_id>/",
        views.AdminDepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path("courses/", views.AdminCourseListView.as_view(), name="course-list"),
    path(
        "courses/<uuid:course_id>/",
        views.AdminCourseDetailView.as_view(),
        name="course-detail",
    ),
    path("units/", views.AdminUnitListView.as_view(), name="unit-list"),
    path(
        "units/<uuid:unit_id>/", views.AdminUnitDetailView.as_view(), name="unit-detail"
    ),
    # Backup & System
    path("backup/", backup.create_backup, name="backup-create"),
    path("system-stats/", backup.system_stats, name="system-stats"),
    path("export/", backup.export_data, name="export-data"),
    
    # Gamification Management
    path("gamification/stats/", views.AdminGamificationStatsView.as_view(), name="gamification-stats"),
    path("gamification/badges/", views.AdminBadgeListView.as_view(), name="badge-list"),
    path("gamification/badges/<int:pk>/", views.AdminBadgeDetailView.as_view(), name="badge-detail"),
    path("gamification/badges/<int:badge_id>/earners/", views.AdminBadgeEarnersView.as_view(), name="badge-earners"),
    path("gamification/users/<int:user_id>/", views.AdminUserGamificationView.as_view(), name="user-gamification"),
    path("gamification/leaderboard/", views.AdminLeaderboardView.as_view(), name="leaderboard"),
    path("gamification/leaderboard/refresh/", views.AdminLeaderboardRefreshView.as_view(), name="leaderboard-refresh"),
    path("gamification/points-config/", views.AdminPointsConfigurationView.as_view(), name="points-config"),
    path("gamification/award-points/", views.AdminAwardPointsView.as_view(), name="award-points"),
    
    # Email Campaign Management
    path("email-campaigns/", views.AdminEmailCampaignListView.as_view(), name="campaign-list"),
    path("email-campaigns/create/", views.AdminEmailCampaignCreateView.as_view(), name="campaign-create"),
    path("email-campaigns/<uuid:campaign_id>/", views.AdminEmailCampaignDetailView.as_view(), name="campaign-detail"),
    path("email-campaigns/<uuid:campaign_id>/send/", views.AdminEmailCampaignSendView.as_view(), name="campaign-send"),
    path("email-campaigns/<uuid:campaign_id>/cancel/", views.AdminEmailCampaignCancelView.as_view(), name="campaign-cancel"),
    path("email-campaigns/<uuid:campaign_id>/delete/", views.AdminEmailCampaignDeleteView.as_view(), name="campaign-delete"),
    path("email-campaigns/stats/", views.AdminEmailCampaignStatsView.as_view(), name="campaign-stats"),
    
    # API Usage Analytics
    path("api-usage/", views.AdminAPIUsageStatsView.as_view(), name="api-usage-stats"),
    path("api-usage/endpoint/", views.AdminAPIEndpointDetailView.as_view(), name="api-usage-endpoint"),
    path("api-usage/users/<int:user_id>/", views.AdminAPIUsageUserView.as_view(), name="api-usage-user"),
    
    # AI Content Moderation
    path("ai-moderation/queue/", views.AIModerationQueueView.as_view(), name="ai-moderation-queue"),
    path("ai-moderation/analyze/", views.AIModerationAnalyzeView.as_view(), name="ai-moderation-analyze"),
    path("ai-moderation/batch/", views.AIModerationBatchView.as_view(), name="ai-moderation-batch"),
    path("ai-moderation/stats/", views.AIModerationStatsView.as_view(), name="ai-moderation-stats"),
    
    # Predictive Analytics
    path("predictive/engagement/", views.PredictiveEngagementView.as_view(), name="predictive-engagement"),
    path("predictive/churn-risk/", views.PredictiveChurnRiskView.as_view(), name="predictive-churn-risk"),
    path("predictive/content-trends/", views.PredictiveContentTrendsView.as_view(), name="predictive-content-trends"),
    path("predictive/summary/", views.PredictiveSummaryView.as_view(), name="predictive-summary"),
    
    # Dashboard Builder
    path("dashboard/widgets/", views.DashboardWidgetsView.as_view(), name="dashboard-widgets"),
    path("dashboard/layouts/", views.DashboardLayoutsView.as_view(), name="dashboard-layouts"),
    path("dashboard/layouts/<str:layout_id>/", views.DashboardLayoutDetailView.as_view(), name="dashboard-layout-detail"),
    
    # Multi-tenant Admin
    path("scope/", views.AdminScopeView.as_view(), name="admin-scope"),
    path("feature-access/", views.AdminFeatureAccessView.as_view(), name="feature-access"),
    
    # Report Builder
    path("reports/", views.ReportListView.as_view(), name="report-list"),
    path("reports/generate/", views.ReportGenerateView.as_view(), name="report-generate"),
    path("reports/summary/", views.ReportSummaryView.as_view(), name="report-summary"),
    
    # Bulk Operations
    path("bulk/resources/update/", views.BulkResourceUpdateView.as_view(), name="bulk-resource-update"),
    path("bulk/resources/delete/", views.BulkResourceDeleteView.as_view(), name="bulk-resource-delete"),
    path("bulk/moderation/", views.BulkModerationView.as_view(), name="bulk-moderation"),
]
