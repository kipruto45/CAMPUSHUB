"""
Serializers for Library & Storage Management Module.
"""

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from apps.resources.models import PersonalFolder, PersonalResource


class StorageSummarySerializer(serializers.Serializer):
    """Serializer for storage summary."""

    storage_limit_bytes = serializers.IntegerField()
    storage_used_bytes = serializers.IntegerField()
    storage_remaining_bytes = serializers.IntegerField()
    usage_percent = serializers.FloatField()
    total_files = serializers.IntegerField()
    warning_level = serializers.CharField()


class BreadcrumbItemSerializer(serializers.Serializer):
    """Serializer for folder breadcrumb entries."""

    id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField(required=False, allow_blank=True)


class TrashItemSerializer(serializers.ModelSerializer):
    """Serializer for trashed items."""

    original_folder_name = serializers.CharField(
        source="original_folder.name", read_only=True, allow_null=True
    )
    file_url = serializers.SerializerMethodField()
    can_restore = serializers.BooleanField(read_only=True)

    class Meta:
        model = PersonalResource
        fields = [
            "id",
            "title",
            "file_type",
            "file_size",
            "deleted_at",
            "original_folder",
            "original_folder_name",
            "file_url",
            "can_restore",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


@extend_schema_serializer(component_name="LibraryPersonalFolder")
class PersonalFolderSerializer(serializers.ModelSerializer):
    """Serializer for personal folders."""

    file_count = serializers.SerializerMethodField()
    total_size = serializers.SerializerMethodField()
    subfolders_count = serializers.SerializerMethodField()

    class Meta:
        model = PersonalFolder
        ref_name = "LibraryPersonalFolder"
        fields = [
            "id",
            "name",
            "color",
            "parent",
            "is_favorite",
            "file_count",
            "total_size",
            "subfolders_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_file_count(self, obj) -> int:
        return obj.get_file_count()

    def get_total_size(self, obj) -> int:
        return obj.get_total_size()

    def get_subfolders_count(self, obj) -> int:
        return obj.subfolders.count() if hasattr(obj, "subfolders") else 0


@extend_schema_serializer(component_name="LibraryPersonalFolderDetail")
class PersonalFolderDetailSerializer(PersonalFolderSerializer):
    """Detailed serializer for personal folders with subfolders and files."""

    subfolders = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()

    class Meta(PersonalFolderSerializer.Meta):
        ref_name = "LibraryPersonalFolderDetail"
        fields = PersonalFolderSerializer.Meta.fields + [
            "subfolders",
            "files",
            "breadcrumbs",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_subfolders(self, obj):
        subfolders = obj.subfolders.all()
        return PersonalFolderSerializer(
            subfolders, many=True, context=self.context
        ).data

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_files(self, obj):
        files = obj.personal_resources.all()
        return PersonalResourceSerializer(files, many=True, context=self.context).data

    @extend_schema_field(BreadcrumbItemSerializer(many=True))
    def get_breadcrumbs(self, obj):
        return obj.get_breadcrumbs()


class MoveFolderSerializer(serializers.Serializer):
    """Serializer for moving a folder."""

    target_parent_id = serializers.UUIDField(required=False, allow_null=True)


class CreateFolderSerializer(serializers.Serializer):
    """Serializer for creating a folder."""

    name = serializers.CharField(max_length=200)
    parent = serializers.UUIDField(required=False, allow_null=True)
    color = serializers.CharField(max_length=20, required=False, default="#3b82f6")


class RenameFolderSerializer(serializers.Serializer):
    """Serializer for renaming a folder."""

    name = serializers.CharField(max_length=200)


@extend_schema_serializer(component_name="LibraryPersonalResource")
class PersonalResourceSerializer(serializers.ModelSerializer):
    """Serializer for personal resources."""

    file_url = serializers.SerializerMethodField()
    folder_name = serializers.CharField(
        source="folder.name", read_only=True, allow_null=True
    )

    class Meta:
        model = PersonalResource
        ref_name = "LibraryPersonalResource"
        fields = [
            "id",
            "title",
            "file",
            "file_url",
            "file_type",
            "file_size",
            "description",
            "folder",
            "folder_name",
            "is_favorite",
            "last_accessed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "user",
            "file_size",
            "file_type",
            "last_accessed_at",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


@extend_schema_serializer(component_name="LibraryPersonalResourceDetail")
class PersonalResourceDetailSerializer(PersonalResourceSerializer):
    """Detailed serializer for personal resources."""

    breadcrumbs = serializers.SerializerMethodField()

    class Meta(PersonalResourceSerializer.Meta):
        ref_name = "LibraryPersonalResourceDetail"
        fields = PersonalResourceSerializer.Meta.fields + ["breadcrumbs"]

    @extend_schema_field(BreadcrumbItemSerializer(many=True))
    def get_breadcrumbs(self, obj):
        if obj.folder:
            return obj.folder.get_breadcrumbs()
        return []


class UploadFileSerializer(serializers.Serializer):
    """Serializer for uploading a file."""

    title = serializers.CharField(max_length=500, required=False)
    file = serializers.FileField(required=True)
    folder = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, default="", allow_blank=True)


class RenameFileSerializer(serializers.Serializer):
    """Serializer for renaming a file."""

    title = serializers.CharField(max_length=500)


class MoveFileSerializer(serializers.Serializer):
    """Serializer for moving a file."""

    folder_id = serializers.UUIDField(required=False, allow_null=True)


class RestoreFileSerializer(serializers.Serializer):
    """Serializer for restoring a file."""

    file_id = serializers.UUIDField()


class PermanentDeleteSerializer(serializers.Serializer):
    """Serializer for permanently deleting a file."""

    file_id = serializers.UUIDField()


class MoveToTrashSerializer(serializers.Serializer):
    """Serializer for moving a file to trash."""

    file_id = serializers.UUIDField()


class LibraryOverviewSerializer(serializers.Serializer):
    """Serializer for library overview."""

    root_folders = PersonalFolderSerializer(many=True)
    recent_files = PersonalResourceSerializer(many=True)
    favorite_folders = PersonalFolderSerializer(many=True)
    favorite_files = PersonalResourceSerializer(many=True)
    storage_summary = StorageSummarySerializer()


class FileShareSerializer(serializers.Serializer):
    """Serializer for file share response."""

    token = serializers.CharField()
    file_id = serializers.CharField()
    file_title = serializers.CharField()
    file_type = serializers.CharField()
    expires_in = serializers.IntegerField()
    share_url = serializers.SerializerMethodField()
    can_share = serializers.BooleanField(default=True)

    def get_share_url(self, obj):
        request = self.context.get("request")
        if request and obj.get("file_id"):
            base_url = request.build_absolute_uri("/")
            return f"{base_url}share/library/{obj['file_id']}/{obj['token']}/"
        return None


class FilePreviewSerializer(serializers.Serializer):
    """Serializer for file preview information."""

    is_previewable = serializers.BooleanField()
    is_image = serializers.BooleanField()
    is_pdf = serializers.BooleanField()
    preview_type = serializers.CharField()
    file_type = serializers.CharField()
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        return obj.get("file_url")

    def get_thumbnail_url(self, obj):
        return obj.get("thumbnail_url")
