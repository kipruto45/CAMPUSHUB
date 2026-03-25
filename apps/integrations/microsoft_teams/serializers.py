"""
Serializers for Microsoft Teams integration API.
"""

from rest_framework import serializers

from .models import (
    MicrosoftTeamsAccount,
    SyncedAssignment,
    SyncedAnnouncement,
    SyncedChannel,
    SyncedSubmission,
    SyncedTeam,
    SyncState,
)


class MicrosoftTeamsAccountSerializer(serializers.ModelSerializer):
    """Serializer for Microsoft Teams account."""

    class Meta:
        model = MicrosoftTeamsAccount
        fields = [
            "id",
            "microsoft_user_id",
            "email",
            "display_name",
            "sync_status",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedTeamSerializer(serializers.ModelSerializer):
    """Serializer for synced teams."""

    class Meta:
        model = SyncedTeam
        fields = [
            "id",
            "team_id",
            "display_name",
            "description",
            "visibility",
            "owner_id",
            "linked_unit",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedChannelSerializer(serializers.ModelSerializer):
    """Serializer for synced channels."""

    class Meta:
        model = SyncedChannel
        fields = [
            "id",
            "channel_id",
            "display_name",
            "description",
            "is_general",
            "web_url",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for synced assignments."""

    class Meta:
        model = SyncedAssignment
        fields = [
            "id",
            "assignment_id",
            "display_name",
            "instructions",
            "status",
            "due_date_time",
            "due_date_includes_time",
            "grading_type",
            "max_points",
            "web_url",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for synced submissions."""

    class Meta:
        model = SyncedSubmission
        fields = [
            "id",
            "submission_id",
            "student_email",
            "state",
            "grade",
            "feedback",
            "submitted_at",
            "returned_at",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedAnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for synced announcements."""

    class Meta:
        model = SyncedAnnouncement
        fields = [
            "id",
            "announcement_id",
            "topic",
            "summary",
            "body",
            "is_pinned",
            "web_url",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncStateSerializer(serializers.ModelSerializer):
    """Serializer for sync state history."""

    class Meta:
        model = SyncState
        fields = [
            "id",
            "sync_type",
            "result",
            "started_at",
            "completed_at",
            "teams_count",
            "channels_count",
            "assignments_count",
            "announcements_count",
            "submissions_count",
            "errors",
            "created_at",
        ]
        read_only_fields = fields


class MicrosoftTeamsStatusSerializer(serializers.Serializer):
    """Serializer for integration status response."""

    is_connected = serializers.BooleanField()
    account = MicrosoftTeamsAccountSerializer(required=False)
    last_sync = SyncStateSerializer(required=False)
    synced_teams_count = serializers.IntegerField()
    synced_assignments_count = serializers.IntegerField()


class MicrosoftTeamsConnectResponseSerializer(serializers.Serializer):
    """Serializer for OAuth connect response."""

    authorization_url = serializers.URLField()
    state = serializers.CharField()


class MicrosoftTeamsSyncResponseSerializer(serializers.Serializer):
    """Serializer for sync trigger response."""

    sync_started = serializers.BooleanField()
    sync_state = SyncStateSerializer()