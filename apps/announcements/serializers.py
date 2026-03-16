"""
Serializers for announcements app.
"""

from rest_framework import serializers

from apps.core.utils import format_file_size

from .models import Announcement, AnnouncementAttachment


class AnnouncementAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for announcement attachments."""

    file_url = serializers.SerializerMethodField()
    formatted_file_size = serializers.SerializerMethodField()

    class Meta:
        model = AnnouncementAttachment
        fields = [
            "id",
            "file",
            "file_url",
            "filename",
            "file_size",
            "formatted_file_size",
            "file_type",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "file_url",
            "filename",
            "file_size",
            "formatted_file_size",
            "file_type",
            "created_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def get_formatted_file_size(self, obj) -> str:
        return format_file_size(int(obj.file_size or 0))


class AnnouncementReadSerializer(serializers.ModelSerializer):
    """Shared read serializer for announcement list/detail payloads."""

    announcement_type_display = serializers.CharField(
        source="get_announcement_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    target_summary = serializers.CharField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, allow_null=True
    )
    attachments = AnnouncementAttachmentSerializer(many=True, read_only=True)
    attachment_count = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()
    attachment_size = serializers.SerializerMethodField()

    def _get_first_attachment(self, obj) -> AnnouncementAttachment | None:
        attachments = getattr(obj, "_prefetched_objects_cache", {}).get("attachments")
        if attachments is not None:
            return attachments[0] if attachments else None
        return obj.attachments.order_by("created_at").first()

    def get_attachment_count(self, obj) -> int:
        attachments = getattr(obj, "_prefetched_objects_cache", {}).get("attachments")
        if attachments is not None:
            return len(attachments)
        return obj.attachments.count()

    def get_attachment_url(self, obj) -> str:
        attachment = self._get_first_attachment(obj)
        if not attachment or not attachment.file:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(attachment.file.url)
        return attachment.file.url

    def get_attachment_name(self, obj) -> str:
        attachment = self._get_first_attachment(obj)
        return attachment.filename if attachment else ""

    def get_attachment_type(self, obj) -> str:
        attachment = self._get_first_attachment(obj)
        return attachment.file_type if attachment else ""

    def get_attachment_size(self, obj) -> str:
        attachment = self._get_first_attachment(obj)
        if not attachment:
            return ""
        return format_file_size(int(attachment.file_size or 0))


class AnnouncementListSerializer(AnnouncementReadSerializer):
    """Serializer for announcement list."""

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "slug",
            "announcement_type",
            "announcement_type_display",
            "status",
            "status_display",
            "is_pinned",
            "target_faculty",
            "target_department",
            "target_course",
            "target_year_of_study",
            "target_summary",
            "published_at",
            "created_by_name",
            "attachments",
            "attachment_count",
            "attachment_url",
            "attachment_name",
            "attachment_type",
            "attachment_size",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AnnouncementDetailSerializer(AnnouncementReadSerializer):
    """Serializer for announcement detail."""

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "slug",
            "content",
            "announcement_type",
            "announcement_type_display",
            "status",
            "status_display",
            "is_pinned",
            "target_faculty",
            "target_department",
            "target_course",
            "target_year_of_study",
            "target_summary",
            "published_at",
            "created_by",
            "created_by_name",
            "attachments",
            "attachment_count",
            "attachment_url",
            "attachment_name",
            "attachment_type",
            "attachment_size",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    """Shared serializer for admin announcement create/update operations."""

    attachments = AnnouncementAttachmentSerializer(many=True, read_only=True)
    attachment_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
    )
    remove_attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Announcement
        fields = [
            "id",
            "slug",
            "title",
            "content",
            "announcement_type",
            "status",
            "target_faculty",
            "target_department",
            "target_course",
            "target_year_of_study",
            "is_pinned",
            "published_at",
            "attachments",
            "attachment_files",
            "remove_attachment_ids",
        ]
        read_only_fields = ["id", "slug", "attachments"]

    def _get_request_values(self, key: str):
        request = self.context.get("request")
        if not request:
            return []

        if hasattr(request.FILES, "getlist") and key == "attachment_files":
            files = [file_obj for file_obj in request.FILES.getlist(key) if file_obj]
            if files:
                return files

        if hasattr(request.data, "getlist"):
            values = [value for value in request.data.getlist(key) if value not in (None, "")]
            if values:
                return values

        raw_value = request.data.get(key)
        if raw_value in (None, ""):
            return []
        if isinstance(raw_value, (list, tuple)):
            return [value for value in raw_value if value not in (None, "")]
        return [raw_value]

    def _apply_attachment_changes(self, announcement, validated_data):
        attachment_files = validated_data.pop("attachment_files", [])
        remove_attachment_ids = validated_data.pop("remove_attachment_ids", [])

        if not attachment_files:
            attachment_files = self._get_request_values("attachment_files")
        if not remove_attachment_ids:
            remove_attachment_ids = self._get_request_values("remove_attachment_ids")

        if remove_attachment_ids:
            announcement.attachments.filter(id__in=remove_attachment_ids).delete()

        for file_obj in attachment_files:
            AnnouncementAttachment.objects.create(
                announcement=announcement,
                file=file_obj,
            )

        prefetched_cache = getattr(announcement, "_prefetched_objects_cache", None)
        if isinstance(prefetched_cache, dict):
            prefetched_cache.pop("attachments", None)


class AnnouncementCreateSerializer(AnnouncementWriteSerializer):
    """Serializer for creating announcements."""

    def create(self, validated_data):
        attachment_files = validated_data.pop("attachment_files", [])
        validated_data.pop("remove_attachment_ids", None)
        validated_data["created_by"] = self.context["request"].user
        announcement = super().create(validated_data)
        self._apply_attachment_changes(
            announcement,
            {"attachment_files": attachment_files},
        )
        return announcement


class AnnouncementUpdateSerializer(AnnouncementWriteSerializer):
    """Serializer for updating announcements."""

    def update(self, instance, validated_data):
        attachment_files = validated_data.pop("attachment_files", [])
        remove_attachment_ids = validated_data.pop("remove_attachment_ids", [])
        announcement = super().update(instance, validated_data)
        self._apply_attachment_changes(
            announcement,
            {
                "attachment_files": attachment_files,
                "remove_attachment_ids": remove_attachment_ids,
            },
        )
        return announcement
