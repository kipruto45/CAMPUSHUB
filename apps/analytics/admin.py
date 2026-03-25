"""
Analytics admin configuration.
"""

from django.contrib import admin
from django.db.models import Count, Avg, Sum
from django.shortcuts import render
from django.http import HttpResponseRedirect

from .models import (AnalyticsEvent, Cohort, DailyMetric,
                    LearningInsight, UserActivitySummary)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "user", "event_name", "timestamp"]
    list_filter = ["event_type", "timestamp"]
    search_fields = ["user__username", "event_name"]
    date_hierarchy = "timestamp"
    
    readonly_fields = ["id", "timestamp"]
    fieldsets = [
        ("Event", {
            "fields": ["id", "event_type", "event_name"]
        }),
        ("User", {
            "fields": ["user", "session_id"]
        }),
        ("Context", {
            "fields": ["resource_id", "course_id", "unit_id", "properties"]
        }),
        ("Attribution", {
            "fields": ["referrer", "utm_source", "utm_medium", "utm_campaign"]
        }),
        ("Device", {
            "fields": ["device_type", "browser", "os"]
        }),
        ("Timestamp", {
            "fields": ["timestamp"]
        }),
    ]


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ["date", "total_users", "active_users", "new_signups", "total_resources", "total_downloads"]
    list_filter = ["date"]
    date_hierarchy = "date"
    
    readonly_fields = ["date"]


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ["cohort_date", "cohort_type", "initial_users", "total_retained", "retention_rate"]
    list_filter = ["cohort_type"]
    date_hierarchy = "cohort_date"
    
    change_list_template = "admin/analytics/cohort_change_list.html"
    
    def changelist_view(self, request, extra_context=None):
        """Add retention summary to changelist."""
        from apps.analytics.services import CohortAnalysisService
        
        retention_report = CohortAnalysisService.get_retention_report()
        extra_context = extra_context or {}
        extra_context["retention_report"] = retention_report
        
        return super().changelog_view(request, extra_context)
    
    def get_urls(self):
        """Add custom URLs for retention report."""
        from django.urls import path
        
        urls = super().get_urls()
        urls.insert(0, path(
            "retention-report/",
            self.admin_site.admin_view(self.retention_report_view),
            name="analytics_cohort_retention"
        ))
        return urls
    
    def retention_report_view(self, request):
        """Show retention report page."""
        from apps.analytics.services import CohortAnalysisService
        
        report = CohortAnalysisService.get_retention_report()
        
        return render(request, "admin/analytics/retention_report.html", {
            "title": "Cohort Retention Report",
            "report": report,
        })


@admin.register(UserActivitySummary)
class UserActivitySummaryAdmin(admin.ModelAdmin):
    list_display = ["user", "period_start", "period_type", "page_views", "downloads", "current_streak_days"]
    list_filter = ["period_type", "period_start"]
    search_fields = ["user__username"]
    date_hierarchy = "period_start"


@admin.register(LearningInsight)
class LearningInsightAdmin(admin.ModelAdmin):
    list_display = ["user", "insight_type", "title", "priority", "is_read", "created_at"]
    list_filter = ["insight_type", "priority", "is_read"]
    search_fields = ["user__username", "title", "description"]
    date_hierarchy = "created_at"
    
    actions = ["mark_as_read", "send_notification"]
    
    @admin.action(description="Mark selected insights as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, "Insights marked as read.")
    
    @admin.action(description="Send notification for insights")
    def send_notification(self, request, queryset):
        from apps.notifications.models import Notification
        
        for insight in queryset:
            Notification.objects.create(
                recipient=insight.user,
                title=insight.title,
                message=insight.description[:100],
                notification_type="insight",
                link=insight.action_url or "/",
            )
        
        self.message_user(request, f"Notifications sent for {queryset.count()} insights.")


# Custom admin views for analytics dashboard
class AnalyticsDashboardMixin:
    """Mixin to add analytics cards to admin dashboard."""
    
    def get_urls(self):
        """Add analytics dashboard URL."""
        from django.urls import path
        
        urls = super().get_urls()
        urls.insert(0, path(
            "dashboard/",
            self.admin_site.admin_view(self.analytics_dashboard),
            name="analytics_dashboard"
        ))
        return urls
    
    def analytics_dashboard(self, request):
        """Show analytics dashboard."""
        from apps.analytics.services import AdminAnalyticsService
        
        summary = AdminAnalyticsService.get_dashboard_summary()
        realtime = AdminAnalyticsService.get_realtime_stats()
        
        return render(request, "admin/analytics/dashboard.html", {
            "title": "Analytics Dashboard",
            "summary": summary,
            "realtime": realtime,
        })