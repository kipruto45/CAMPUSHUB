"""
Serializers for activity app.
"""

from rest_framework import serializers

from .models import RecentActivity


class RecentActivitySerializer(serializers.ModelSerializer):
    """Serializer for recent activity."""

    activity_type_display = serializers.CharField(
        source="get_activity_type_display", read_only=True
    )
    target_title = serializers.CharField(read_only=True)
    target_type = serializers.CharField(read_only=True)
    resource_type = serializers.CharField(
        source="resource.resource_type", read_only=True, allow_null=True
    )
    file_type = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = RecentActivity
        fields = [
            "id",
            "activity_type",
            "activity_type_display",
            "target_title",
            "target_type",
            "resource",
            "personal_file",
            "bookmark",
            "resource_type",
            "file_type",
            "file_url",
            "metadata",
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

    def get_file_url(self, obj) -> str:
        """Get the file URL."""
        if obj.resource and obj.resource.file:
            return obj.resource.file.url
        elif obj.personal_file and obj.personal_file.file:
            return obj.personal_file.file.url
        return ""


class RecentResourcesSerializer(serializers.ModelSerializer):
    """Serializer for recent resources."""

    title = serializers.CharField(source="resource.title", read_only=True)
    resource_type = serializers.CharField(
        source="resource.resource_type", read_only=True
    )
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = RecentActivity
        fields = [
            "id",
            "title",
            "resource_type",
            "file_type",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_type(self, obj) -> str:
        if obj.resource and obj.resource.file:
            name = obj.resource.file.name
            return name.split(".")[-1].lower() if "." in name else ""
        return ""


class RecentFilesSerializer(serializers.ModelSerializer):
    """Serializer for recent personal files."""

    name = serializers.CharField(source="personal_file.title", read_only=True)
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = RecentActivity
        fields = [
            "id",
            "name",
            "file_type",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_type(self, obj) -> str:
        if obj.personal_file and obj.personal_file.file:
            name = obj.personal_file.file.name
            return name.split(".")[-1].lower() if "." in name else ""
        return ""


class ActivityStatsSerializer(serializers.Serializer):
    """Serializer for activity statistics."""

    total_activities = serializers.IntegerField()
    viewed_count = serializers.IntegerField()
    downloaded_count = serializers.IntegerField()
    bookmarked_count = serializers.IntegerField()
    opened_files_count = serializers.IntegerField()
