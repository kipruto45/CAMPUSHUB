"""
Serializers for downloads app.
"""

from rest_framework import serializers

from apps.core.storage.utils import build_storage_download_path

from .models import Download


class DownloadHistorySerializer(serializers.ModelSerializer):
    """Serializer for download history."""

    resource_title = serializers.CharField(
        source="resource.title", read_only=True, allow_null=True
    )
    resource_type = serializers.CharField(
        source="resource.resource_type", read_only=True, allow_null=True
    )
    personal_file_name = serializers.CharField(
        source="personal_file.title", read_only=True, allow_null=True
    )
    download_type = serializers.CharField(read_only=True)
    download_title = serializers.CharField(read_only=True)
    file_type = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Download
        fields = [
            "id",
            "download_type",
            "download_title",
            "resource",
            "resource_title",
            "resource_type",
            "personal_file",
            "personal_file_name",
            "file_type",
            "file_url",
            "ip_address",
            "user_agent",
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
        """Get the download URL."""
        if obj.resource and obj.resource.file:
            path = build_storage_download_path(obj.resource.file.name, public=True)
        elif obj.personal_file and obj.personal_file.file:
            path = build_storage_download_path(obj.personal_file.file.name, public=False)
        else:
            return ""

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(path)
        return path


class DownloadStatsSerializer(serializers.Serializer):
    """Serializer for download statistics."""

    total_downloads = serializers.IntegerField()
    unique_resources = serializers.IntegerField()
    recent_downloads = DownloadHistorySerializer(many=True)


class ResourceDownloadSerializer(serializers.Serializer):
    """Serializer for resource download response."""

    download_id = serializers.UUIDField()
    file_url = serializers.URLField()
    file_name = serializers.CharField()
    resource_title = serializers.CharField(allow_null=True)
    message = serializers.CharField()


class PersonalFileDownloadSerializer(serializers.Serializer):
    """Serializer for personal file download response."""

    download_id = serializers.UUIDField()
    file_url = serializers.URLField()
    file_name = serializers.CharField()
    message = serializers.CharField()
