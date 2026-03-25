"""
Serializers for Google Classroom integration API.
"""

from rest_framework import serializers

from .models import (
    GoogleClassroomAccount,
    SyncedAssignment,
    SyncedAnnouncement,
    SyncedCourse,
    SyncedSubmission,
    SyncState,
)


class GoogleClassroomAccountSerializer(serializers.ModelSerializer):
    """Serializer for Google Classroom account."""

    class Meta:
        model = GoogleClassroomAccount
        fields = [
            "id",
            "google_user_id",
            "email",
            "sync_status",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SyncedCourseSerializer(serializers.ModelSerializer):
    """Serializer for synced courses."""

    class Meta:
        model = SyncedCourse
        fields = [
            "id",
            "google_course_id",
            "name",
            "section",
            "description",
            "room",
            "owner_id",
            "enrollment_code",
            "linked_unit",
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
            "google_assignment_id",
            "title",
            "description",
            "state",
            "due_date",
            "max_points",
            "work_type",
            "alternate_link",
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
            "google_submission_id",
            "student_email",
            "state",
            "assigned_grade",
            "draft_grade",
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
            "google_announcement_id",
            "text",
            "state",
            "scheduled_date",
            "alternate_link",
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
            "courses_count",
            "assignments_count",
            "announcements_count",
            "submissions_count",
            "errors",
            "created_at",
        ]
        read_only_fields = fields


class GoogleClassroomStatusSerializer(serializers.Serializer):
    """Serializer for integration status response."""

    is_connected = serializers.BooleanField()
    account = GoogleClassroomAccountSerializer(required=False)
    last_sync = SyncStateSerializer(required=False)
    synced_courses_count = serializers.IntegerField()
    synced_assignments_count = serializers.IntegerField()


class GoogleClassroomConnectResponseSerializer(serializers.Serializer):
    """Serializer for OAuth connect response."""

    authorization_url = serializers.URLField()
    state = serializers.CharField()


class GoogleClassroomSyncResponseSerializer(serializers.Serializer):
    """Serializer for sync trigger response."""

    sync_started = serializers.BooleanField()
    sync_state = SyncStateSerializer()