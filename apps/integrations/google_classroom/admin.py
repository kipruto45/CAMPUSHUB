"""
Admin configuration for Google Classroom integration.
"""

from django.contrib import admin

from .models import (
    GoogleClassroomAccount,
    SyncedAssignment,
    SyncedAnnouncement,
    SyncedCourse,
    SyncedSubmission,
    SyncState,
)


@admin.register(GoogleClassroomAccount)
class GoogleClassroomAccountAdmin(admin.ModelAdmin):
    """Admin for Google Classroom accounts."""

    list_display = ["email", "google_user_id", "sync_status", "last_sync_at"]
    list_filter = ["sync_status"]
    search_fields = ["email", "google_user_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SyncedCourse)
class SyncedCourseAdmin(admin.ModelAdmin):
    """Admin for synced courses."""

    list_display = ["name", "google_course_id", "account", "last_synced_at"]
    list_filter = ["account"]
    search_fields = ["name", "google_course_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SyncedAssignment)
class SyncedAssignmentAdmin(admin.ModelAdmin):
    """Admin for synced assignments."""

    list_display = ["title", "google_assignment_id", "synced_course", "due_date", "state"]
    list_filter = ["state", "synced_course"]
    search_fields = ["title", "google_assignment_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SyncedSubmission)
class SyncedSubmissionAdmin(admin.ModelAdmin):
    """Admin for synced submissions."""

    list_display = ["student_email", "synced_assignment", "state", "assigned_grade"]
    list_filter = ["state", "synced_assignment"]
    search_fields = ["student_email", "google_submission_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SyncedAnnouncement)
class SyncedAnnouncementAdmin(admin.ModelAdmin):
    """Admin for synced announcements."""

    list_display = ["google_announcement_id", "synced_course", "state", "scheduled_date"]
    list_filter = ["state", "synced_course"]
    search_fields = ["text", "google_announcement_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    """Admin for sync history."""

    list_display = ["account", "sync_type", "result", "started_at", "completed_at"]
    list_filter = ["sync_type", "result"]
    readonly_fields = ["created_at", "updated_at"]