"""
Serializers for favorites app.
"""

from rest_framework import serializers

from .models import Favorite, FavoriteType


class FavoriteListSerializer(serializers.ModelSerializer):
    """Serializer for favorite list."""

    favorite_type_display = serializers.CharField(
        source="get_favorite_type_display", read_only=True
    )
    target_title = serializers.CharField(read_only=True)
    resource_type = serializers.CharField(
        source="resource.resource_type", read_only=True, allow_null=True
    )
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = [
            "id",
            "favorite_type",
            "favorite_type_display",
            "target_title",
            "resource",
            "personal_file",
            "personal_folder",
            "resource_type",
            "file_type",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_type(self, obj) -> str:
        """Get file extension."""
        file_field = None
        if obj.resource and obj.resource.file:
            file_field = obj.resource.file
        elif obj.personal_file and obj.personal_file.file:
            file_field = obj.personal_file.file

        if file_field:
            name = file_field.name
            ext = name.split(".")[-1].lower() if "." in name else ""
            return ext
        return ""


class FavoriteCreateSerializer(serializers.Serializer):
    """Serializer for creating a favorite."""

    favorite_type = serializers.ChoiceField(choices=FavoriteType.CHOICES)
    resource_id = serializers.UUIDField(required=False)
    personal_file_id = serializers.UUIDField(required=False)
    personal_folder_id = serializers.UUIDField(required=False)

    def validate(self, data):
        has_resource = data.get("resource_id") is not None
        has_file = data.get("personal_file_id") is not None
        has_folder = data.get("personal_folder_id") is not None
        provided = [has_resource, has_file, has_folder]
        if sum(provided) != 1:
            raise serializers.ValidationError(
                "Exactly one of resource_id, personal_file_id, or personal_folder_id must be provided."
            )

        favorite_type = data.get("favorite_type")
        if favorite_type == FavoriteType.RESOURCE and not has_resource:
            raise serializers.ValidationError(
                {"resource_id": "resource_id is required for resource favorites."}
            )
        if favorite_type == FavoriteType.PERSONAL_FILE and not has_file:
            raise serializers.ValidationError(
                {"personal_file_id": "personal_file_id is required for file favorites."}
            )
        if favorite_type == FavoriteType.FOLDER and not has_folder:
            raise serializers.ValidationError(
                {"personal_folder_id": "personal_folder_id is required for folder favorites."}
            )

        return data


class FavoriteToggleSerializer(serializers.Serializer):
    """Serializer for toggling favorite status."""

    resource_id = serializers.UUIDField(required=False)
    personal_file_id = serializers.UUIDField(required=False)
    personal_folder_id = serializers.UUIDField(required=False)

    def validate(self, data):
        has_resource = data.get("resource_id") is not None
        has_file = data.get("personal_file_id") is not None
        has_folder = data.get("personal_folder_id") is not None
        if sum([has_resource, has_file, has_folder]) != 1:
            raise serializers.ValidationError(
                "Exactly one of resource_id, personal_file_id, or personal_folder_id must be provided."
            )
        return data


class FavoriteStatsSerializer(serializers.Serializer):
    """Serializer for favorite statistics."""

    total_favorites = serializers.IntegerField()
    resource_count = serializers.IntegerField()
    personal_file_count = serializers.IntegerField()
    folder_count = serializers.IntegerField()
