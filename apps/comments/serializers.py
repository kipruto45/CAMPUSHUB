"""
Serializers for comments app.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model."""

    user_details = UserSerializer(source="user", read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "user_details",
            "resource",
            "parent",
            "content",
            "is_edited",
            "is_deleted",
            "is_locked",
            "replies_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_edited",
            "is_deleted",
            "is_locked",
            "created_at",
            "updated_at",
        ]

    def get_replies_count(self, obj) -> int:
        return obj.replies.count() if obj.replies.exists() else 0


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments."""

    class Meta:
        model = Comment
        fields = ["resource", "parent", "content"]
        extra_kwargs = {
            "resource": {"required": False},
        }

    def validate(self, attrs):
        resource = attrs.get("resource")
        context_resource_id = self.context.get("resource_id")
        if not resource and not context_resource_id:
            raise serializers.ValidationError({"resource": "Resource is required."})
        parent = attrs.get("parent")
        if parent and parent.is_locked:
            raise serializers.ValidationError("This thread is locked by moderation.")
        if parent and parent.is_deleted:
            raise serializers.ValidationError("Cannot reply to a deleted comment.")
        content = (attrs.get("content") or "").strip()
        if not content:
            raise serializers.ValidationError(
                {"content": "Comment content cannot be empty."}
            )
        return attrs


class ReplySerializer(serializers.ModelSerializer):
    """Serializer for comment replies."""

    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "user_details",
            "resource",
            "parent",
            "content",
            "is_edited",
            "is_deleted",
            "is_locked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_edited",
            "is_deleted",
            "is_locked",
            "created_at",
            "updated_at",
        ]
