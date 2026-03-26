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
    path(
        "users/invitations/",
        views.AdminRoleInvitationListCreateView.as_view(),
        name="role-invitation-list",
    ),
    path(
        "users/invitations/options/",
        views.AdminInvitationRoleOptionsView.as_view(),
        name="role-invitation-options",
    ),
    path(
        "users/invitations/bulk/",
        views.AdminRoleInvitationBulkCreateView.as_view(),
        name="role-invitation-bulk",
    ),
    path(
        "users/invitations/validate/<str:token>/",
        views.AdminRoleInvitationValidateView.as_view(),
        name="role-invitation-validate",
    ),
    path(
        "users/invitations/accept/",
        views.AdminRoleInvitationAcceptView.as_view(),
        name="role-invitation-accept",
    ),
    path(
        "users/invitations/<uuid:invitation_id>/revoke/",
        views.AdminRoleInvitationRevokeView.as_view(),
        name="role-invitation-revoke",
    ),
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
    path(
        "users/<int:user_id>/impersonate/",
        views.AdminUserImpersonateView.as_view(),
        name="user-impersonate",
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
    # Referral Management
    path("referrals/", views.AdminReferralListView.as_view(), name="referral-list"),
    path(
        "referrals/<uuid:referral_id>/",
        views.AdminReferralDetailView.as_view(),
        name="referral-detail",
    ),
    path(
        "referrals/reward-tiers/",
        views.AdminRewardTierListView.as_view(),
        name="referral-reward-tier-list",
    ),
    path(
        "referrals/reward-tiers/<int:tier_id>/",
        views.AdminRewardTierDetailView.as_view(),
        name="referral-reward-tier-detail",
    ),
    # Payments Management
    path("payments/", views.AdminPaymentListView.as_view(), name="admin-payment-list"),
    path(
        "payments/<uuid:payment_id>/",
        views.AdminPaymentDetailView.as_view(),
        name="admin-payment-detail",
    ),
    path(
        "subscriptions/",
        views.AdminSubscriptionListView.as_view(),
        name="admin-subscription-list",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/",
        views.AdminSubscriptionDetailView.as_view(),
        name="admin-subscription-detail",
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

    # Content Operations
    path(
        "calendar/events/",
        views.AdminContentCalendarEventListCreateView.as_view(),
        name="content-calendar-events",
    ),
    path("incidents/", views.AdminIncidentListCreateView.as_view(), name="incident-list"),
    path(
        "incidents/<uuid:incident_id>/status/",
        views.AdminIncidentStatusUpdateView.as_view(),
        name="incident-status",
    ),
    path("funnels/", views.AdminFunnelListView.as_view(), name="funnel-list"),
    path(
        "funnels/<uuid:funnel_id>/dropoff/",
        views.AdminFunnelDropoffView.as_view(),
        name="funnel-dropoff",
    ),
    path("api-keys/", views.AdminAPIKeyListCreateView.as_view(), name="api-key-list"),
    path(
        "api-keys/<uuid:key_id>/",
        views.AdminAPIKeyDetailView.as_view(),
        name="api-key-detail",
    ),
    path(
        "api-keys/<uuid:key_id>/revoke/",
        views.AdminAPIKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
    path("workflows/", views.AdminWorkflowListCreateView.as_view(), name="workflow-list"),
    path(
        "workflows/<uuid:workflow_id>/",
        views.AdminWorkflowDetailView.as_view(),
        name="workflow-detail",
    ),
    path(
        "workflows/<uuid:workflow_id>/executions/",
        views.AdminWorkflowExecutionListView.as_view(),
        name="workflow-executions",
    ),
    path(
        "workflows/<uuid:workflow_id>/run/",
        views.AdminWorkflowRunView.as_view(),
        name="workflow-run",
    ),
    path("webhooks/", views.AdminWebhookListCreateView.as_view(), name="webhook-list"),
    path(
        "webhooks/<uuid:webhook_id>/",
        views.AdminWebhookDetailView.as_view(),
        name="webhook-detail",
    ),
    path(
        "webhooks/<uuid:webhook_id>/test/",
        views.AdminWebhookTestView.as_view(),
        name="webhook-test",
    ),
    path("audit/", views.AdminAuditLogListView.as_view(), name="audit-log"),
    
    # Multi-tenant Admin
    path("scope/", views.AdminScopeView.as_view(), name="admin-scope"),
    path("feature-access/", views.AdminFeatureAccessView.as_view(), name="feature-access"),
    
    # Report Builder
    path("reports/", views.ReportListView.as_view(), name="report-list"),
    path("reports/generate/", views.ReportGenerateView.as_view(), name="report-generate"),
    path("reports/summary/", views.ReportSummaryView.as_view(), name="report-summary"),
    path(
        "report-builder/reports/",
        views.ReportListView.as_view(),
        name="report-builder-list",
    ),
    path(
        "report-builder/reports/generate/",
        views.ReportGenerateView.as_view(),
        name="report-builder-generate",
    ),
    path(
        "report-builder/reports/summary/",
        views.ReportSummaryView.as_view(),
        name="report-builder-summary",
    ),
    
    # Bulk Operations
    path("bulk/resources/update/", views.BulkResourceUpdateView.as_view(), name="bulk-resource-update"),
    path("bulk/resources/delete/", views.BulkResourceDeleteView.as_view(), name="bulk-resource-delete"),
    path("bulk/moderation/", views.BulkModerationView.as_view(), name="bulk-moderation"),
    path("bulk/resources/upload/", views.BulkResourceUploadView.as_view(), name="bulk-resource-upload"),
    path("bulk/resources/upload-by-type/", views.BulkResourceByTypeView.as_view(), name="bulk-resource-upload-type"),

    # Calendar Admin URLs
    path(
        "academic-calendars/",
        views.AdminAcademicCalendarListView.as_view(),
        name="academic-calendar-list",
    ),
    path(
        "academic-calendars/<uuid:calendar_id>/",
        views.AdminAcademicCalendarDetailView.as_view(),
        name="academic-calendar-detail",
    ),
    path(
        "timetables/",
        views.AdminTimetableListView.as_view(),
        name="timetable-list",
    ),
    path(
        "timetables/<uuid:timetable_id>/",
        views.AdminTimetableDetailView.as_view(),
        name="timetable-detail",
    ),
    path(
        "timetable-overrides/",
        views.AdminTimetableOverrideListView.as_view(),
        name="timetable-override-list",
    ),
    path(
        "timetable-overrides/<uuid:override_id>/",
        views.AdminTimetableOverrideDetailView.as_view(),
        name="timetable-override-detail",
    ),
    path(
        "personal-schedules/",
        views.AdminPersonalScheduleListView.as_view(),
        name="personal-schedule-list",
    ),
    path(
        "personal-schedules/<uuid:schedule_id>/",
        views.AdminPersonalScheduleDetailView.as_view(),
        name="personal-schedule-detail",
    ),
    path(
        "schedule-exports/",
        views.AdminScheduleExportListView.as_view(),
        name="schedule-export-list",
    ),
    path(
        "schedule-exports/<uuid:export_id>/",
        views.AdminScheduleExportDetailView.as_view(),
        name="schedule-export-detail",
    ),
    # Calendar Sync Admin URLs
    path(
        "calendar-accounts/",
        views.AdminCalendarAccountListView.as_view(),
        name="calendar-account-list",
    ),
    path(
        "calendar-accounts/<uuid:account_id>/",
        views.AdminCalendarAccountDetailView.as_view(),
        name="calendar-account-detail",
    ),
    path(
        "sync-settings/",
        views.AdminSyncSettingsListView.as_view(),
        name="sync-settings-list",
    ),
    path(
        "sync-settings/<uuid:settings_id>/",
        views.AdminSyncSettingsDetailView.as_view(),
        name="sync-settings-detail",
    ),
    path(
        "synced-events/",
        views.AdminSyncedEventListView.as_view(),
        name="synced-event-list",
    ),
    path(
        "synced-events/<uuid:event_id>/",
        views.AdminSyncedEventDetailView.as_view(),
        name="synced-event-detail",
    ),
]
