"""
Serializers for the Dashboard API.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer


class DashboardUserSummarySerializer(serializers.Serializer):
    """Serializer for user summary in dashboard."""

    user = UserSummarySerializer(read_only=True)
    profile_completion = serializers.IntegerField(read_only=True)
    is_profile_complete = serializers.BooleanField(read_only=True)


class DashboardQuickStatsSerializer(serializers.Serializer):
    """Serializer for quick stats in dashboard."""

    bookmarks_count = serializers.IntegerField(read_only=True)
    personal_files_count = serializers.IntegerField(read_only=True)
    uploads_count = serializers.IntegerField(read_only=True)
    downloads_count = serializers.IntegerField(read_only=True)
    storage_used_mb = serializers.FloatField(read_only=True)
    storage_limit_mb = serializers.FloatField(read_only=True)
    storage_percent_used = serializers.FloatField(read_only=True)


class RecentActivityItemSerializer(serializers.Serializer):
    """Serializer for a single recent activity item."""

    id = serializers.UUIDField(read_only=True)
    type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    url = serializers.CharField(read_only=True, allow_blank=True)


class RecentActivitySerializer(serializers.Serializer):
    """Serializer for recent activity section."""

    recent_uploads = RecentActivityItemSerializer(many=True, read_only=True)
    recent_downloads = RecentActivityItemSerializer(many=True, read_only=True)
    recent_bookmarks = RecentActivityItemSerializer(many=True, read_only=True)


class RecommendationItemSerializer(serializers.Serializer):
    """Serializer for a single recommendation item."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    download_count = serializers.IntegerField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    uploaded_by = serializers.CharField(read_only=True)
    course_name = serializers.CharField(read_only=True, allow_null=True)
    url = serializers.CharField(read_only=True)


class RecommendationsSerializer(serializers.Serializer):
    """Serializer for recommendations section."""

    for_you = RecommendationItemSerializer(many=True, read_only=True)
    trending = RecommendationItemSerializer(many=True, read_only=True)
    course_related = RecommendationItemSerializer(many=True, read_only=True)
    recently_added = RecommendationItemSerializer(many=True, read_only=True)


class AnnouncementSerializer(serializers.Serializer):
    """Serializer for announcements."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class PendingUploadSerializer(serializers.Serializer):
    """Serializer for pending uploads."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    course_name = serializers.CharField(read_only=True, allow_null=True)
    uploaded_at = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)


class PendingUploadsSerializer(serializers.Serializer):
    """Serializer for pending uploads section."""

    pending_approval = PendingUploadSerializer(many=True, read_only=True)
    rejected = PendingUploadSerializer(many=True, read_only=True)
    total_pending = serializers.IntegerField(read_only=True)
    total_rejected = serializers.IntegerField(read_only=True)


class NotificationSummarySerializer(serializers.Serializer):
    """Serializer for notification summary."""

    unread_count = serializers.IntegerField(read_only=True)
    recent_notifications = serializers.ListField(
        child=serializers.DictField(), read_only=True
    )


class DashboardResponseSerializer(serializers.Serializer):
    """Complete dashboard response serializer."""

    user_summary = DashboardUserSummarySerializer(read_only=True)
    quick_stats = DashboardQuickStatsSerializer(read_only=True)
    recent_activity = RecentActivitySerializer(read_only=True)
    recommendations = RecommendationsSerializer(read_only=True)
    announcements = AnnouncementSerializer(many=True, read_only=True)
    pending_uploads = PendingUploadsSerializer(read_only=True)
    notifications = NotificationSummarySerializer(read_only=True)
