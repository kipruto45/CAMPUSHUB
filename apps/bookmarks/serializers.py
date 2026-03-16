"""
Serializers for bookmarks app.
"""

from rest_framework import serializers

from apps.resources.models import Resource
from apps.resources.serializers import ResourceListSerializer

from .models import Bookmark
from .services import BookmarkService


class BookmarkListSerializer(serializers.ModelSerializer):
    """Serializer for bookmark list card data."""

    resource_details = ResourceListSerializer(source="resource", read_only=True)
    saved_at = serializers.DateTimeField(source="created_at", read_only=True)
    title = serializers.CharField(source="resource.title", read_only=True)
    resource_type = serializers.CharField(
        source="resource.resource_type", read_only=True
    )
    course = serializers.CharField(
        source="resource.course.name", read_only=True, allow_null=True
    )
    unit = serializers.CharField(
        source="resource.unit.name", read_only=True, allow_null=True
    )
    upload_date = serializers.DateTimeField(
        source="resource.created_at", read_only=True
    )
    file_type = serializers.CharField(source="resource.file_type", read_only=True)
    rating = serializers.DecimalField(
        source="resource.average_rating", max_digits=3, decimal_places=2, read_only=True
    )

    class Meta:
        model = Bookmark
        fields = [
            "id",
            "resource",
            "resource_details",
            "saved_at",
            "title",
            "resource_type",
            "course",
            "unit",
            "upload_date",
            "file_type",
            "rating",
        ]
        read_only_fields = fields


class BookmarkCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bookmarks."""

    resource = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.all())

    class Meta:
        model = Bookmark
        fields = ["resource"]

    def validate_resource(self, value):
        user = self.context["request"].user
        BookmarkService.validate_resource_bookmarkable(user, value)
        if Bookmark.objects.filter(user=user, resource=value).exists():
            raise serializers.ValidationError("Resource already bookmarked.")
        return value

    def create(self, validated_data):
        return BookmarkService.add_bookmark(
            user=self.context["request"].user,
            resource=validated_data["resource"],
        )


class BookmarkToggleSerializer(serializers.Serializer):
    """Serializer for toggling bookmarks."""

    resource_id = serializers.UUIDField()


# Backward-compatible alias.
BookmarkSerializer = BookmarkListSerializer
