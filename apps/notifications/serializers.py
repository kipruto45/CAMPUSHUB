"""
Serializers for notifications app.
"""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    notification_type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )
    target_resource_title = serializers.CharField(
        source="target_resource.title", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "notification_type_display",
            "is_read",
            "link",
            "target_resource",
            "target_resource_title",
            "target_comment",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification list."""

    notification_type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "notification_type_display",
            "is_read",
            "link",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MarkNotificationReadSerializer(serializers.Serializer):
    """Serializer for marking notification as read."""

    notification_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )


class UnreadCountSerializer(serializers.Serializer):
    """Serializer for unread count response."""

    unread_count = serializers.IntegerField()
