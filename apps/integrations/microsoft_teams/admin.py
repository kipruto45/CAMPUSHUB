"""
Admin configuration for Microsoft Teams integration.
"""

from django.contrib import admin

from .models import (
    MicrosoftTeamsAccount,
    SyncedAssignment,
    SyncedAnnouncement,
    SyncedChannel,
    SyncedSubmission,
    SyncedTeam,
    SyncState,
)


@admin.register(MicrosoftTeamsAccount)
class MicrosoftTeamsAccountAdmin(admin.ModelAdmin):
    list_display = ["email", "display_name", "sync_status", "last_sync_at", "created_at"]
    list_filter = ["sync_status"]
    search_fields = ["email", "display_name", "microsoft_user_id"]
    readonly_fields = ["microsoft_user_id", "access_token", "refresh_token", "token_expires_at"]


@admin.register(SyncedTeam)
class SyncedTeamAdmin(admin.ModelAdmin):
    list_display = ["display_name", "account", "visibility", "last_synced_at", "created_at"]
    list_filter = ["visibility", "account"]
    search_fields = ["display_name", "team_id"]


@admin.register(SyncedChannel)
class SyncedChannelAdmin(admin.ModelAdmin):
    list_display = ["display_name", "synced_team", "is_general", "last_synced_at", "created_at"]
    list_filter = ["is_general", "synced_team"]
    search_fields = ["display_name", "channel_id"]


@admin.register(SyncedAssignment)
class SyncedAssignmentAdmin(admin.ModelAdmin):
    list_display = ["display_name", "synced_team", "status", "due_date_time", "last_synced_at", "created_at"]
    list_filter = ["status", "synced_team"]
    search_fields = ["display_name", "assignment_id"]


@admin.register(SyncedSubmission)
class SyncedSubmissionAdmin(admin.ModelAdmin):
    list_display = ["student_email", "synced_assignment", "state", "grade", "submitted_at", "last_synced_at"]
    list_filter = ["state", "synced_assignment"]
    search_fields = ["student_email", "submission_id"]


@admin.register(SyncedAnnouncement)
class SyncedAnnouncementAdmin(admin.ModelAdmin):
    list_display = ["topic", "synced_channel", "is_pinned", "last_synced_at", "created_at"]
    list_filter = ["is_pinned", "synced_channel"]
    search_fields = ["topic", "announcement_id"]


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ["account", "sync_type", "result", "started_at", "completed_at", "teams_count", "assignments_count"]
    list_filter = ["sync_type", "result"]
    readonly_fields = ["account", "sync_type", "result", "started_at", "completed_at", "errors"]