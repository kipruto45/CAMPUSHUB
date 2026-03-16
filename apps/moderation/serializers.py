"""
Serializers for moderation app.
"""

from rest_framework import serializers

from .models import AdminActivityLog, ModerationLog


class ModerationLogSerializer(serializers.ModelSerializer):
    """Serializer for ModerationLog model."""

    reviewed_by_name = serializers.CharField(
        source="reviewed_by.full_name", read_only=True
    )
    target_type = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()

    class Meta:
        model = ModerationLog
        fields = [
            "id",
            "resource",
            "comment",
            "target_type",
            "target_title",
            "reviewed_by",
            "reviewed_by_name",
            "action",
            "reason",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_target_type(self, obj) -> str:
        if obj.comment_id:
            return "comment"
        if obj.resource_id:
            return "resource"
        if obj.user_id:
            return "user"
        return "unknown"

    def get_target_title(self, obj) -> str | None:
        if obj.comment:
            return f"Comment #{obj.comment_id}"
        if obj.resource:
            return obj.resource.title
        if obj.user:
            return obj.user.email
        return None


class AdminActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for AdminActivityLog model."""

    admin_name = serializers.CharField(source="admin.full_name", read_only=True)
    admin_email = serializers.EmailField(source="admin.email", read_only=True)

    class Meta:
        model = AdminActivityLog
        fields = [
            "id",
            "admin",
            "admin_name",
            "admin_email",
            "action",
            "target_type",
            "target_id",
            "target_title",
            "metadata",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ApproveResourceSerializer(serializers.Serializer):
    """Serializer for approving resources."""

    reason = serializers.CharField(required=False, allow_blank=True)


class RejectResourceSerializer(serializers.Serializer):
    """Serializer for rejecting resources."""

    reason = serializers.CharField(required=True)


class FlagResourceSerializer(serializers.Serializer):
    """Serializer for flagging resources."""

    reason = serializers.CharField(required=False, allow_blank=True)


class ArchiveResourceSerializer(serializers.Serializer):
    """Serializer for archiving resources."""

    reason = serializers.CharField(required=False, allow_blank=True)
