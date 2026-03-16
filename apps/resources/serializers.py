"""
Serializers for resources app.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import (CourseProgress, Folder, FolderItem, PersonalFolder,
                     PersonalResource, Resource, ResourceFile,
                     ResourceRequest, ResourceShareEvent, StorageUpgradeRequest,
                     UserStorage)
from .services import ResourceShareService, ResourceUploadService, calculate_auto_rating
from .validators import sanitize_filename


class ResourceFileSerializer(serializers.ModelSerializer):
    """Serializer for ResourceFile model."""

    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ResourceFile
        fields = [
            "id",
            "file",
            "file_url",
            "filename",
            "file_size",
            "file_type",
            "created_at",
        ]
        read_only_fields = ["id", "filename", "file_size", "file_type", "created_at"]

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class ResourcePreviewSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for resource preview/profile cards.
    Used for quick previews before downloading.
    """

    uploaded_by_name = serializers.SerializerMethodField()
    uploaded_by_avatar = serializers.SerializerMethodField()
    faculty_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    course_code = serializers.SerializerMethodField()
    unit_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    
    # User interactions
    is_bookmarked = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            # Core info
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            
            # File info
            "file",
            "file_url",
            "file_size",
            "file_type",
            "file_icon",
            "thumbnail",
            "thumbnail_url",
            
            # Academic info
            "faculty_name",
            "department_name",
            "course_name",
            "course_code",
            "unit_name",
            "unit_code",
            "semester",
            "year_of_study",
            "tags",
            "tags_list",
            
            # Uploader info
            "uploaded_by",
            "uploaded_by_name",
            "uploaded_by_avatar",
            
            # Engagement stats
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "comments_count",
            "ratings_count",
            
            # Status
            "status",
            "is_public",
            "is_pinned",
            
            # User interactions
            "is_bookmarked",
            "is_favorited",
            "user_rating",
            
            # Timestamps
            "created_at",
            "updated_at",
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            full_name = obj.uploaded_by.get_full_name()
            return full_name if full_name else obj.uploaded_by.email
        return None

    def get_uploaded_by_avatar(self, obj):
        if obj.uploaded_by and hasattr(obj.uploaded_by, 'avatar'):
            return obj.uploaded_by.avatar
        return None

    def get_faculty_name(self, obj):
        return obj.faculty.name if obj.faculty else None

    def get_department_name(self, obj):
        return obj.department.name if obj.department else None

    def get_course_name(self, obj):
        return obj.course.name if obj.course else None

    def get_course_code(self, obj):
        return obj.course.code if obj.course else None

    def get_unit_name(self, obj):
        return obj.unit.name if obj.unit else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit else None

    def get_file_icon(self, obj):
        file_type_icons = {
            'pdf': '📄',
            'doc': '📝',
            'docx': '📝',
            'ppt': '📊',
            'pptx': '📊',
            'xls': '📈',
            'xlsx': '📈',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'png': '🖼️',
            'gif': '🖼️',
            'mp4': '🎬',
            'mp3': '🎵',
            'zip': '📦',
            'rar': '📦',
        }
        return file_type_icons.get(obj.file_type.lower() if obj.file_type else '', '📁')

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_tags_list(self, obj):
        if obj.tags:
            return [tag.strip() for tag in obj.tags.split(',') if tag.strip()]
        return []

    def get_is_bookmarked(self, obj):
        from apps.bookmarks.models import Bookmark
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Bookmark.objects.filter(
                user=request.user, resource=obj
            ).exists()
        return False

    def get_is_favorited(self, obj):
        from apps.favorites.models import Favorite
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, resource=obj
            ).exists()
        return False

    def get_user_rating(self, obj):
        from apps.ratings.models import Rating
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            rating = Rating.objects.filter(
                user=request.user, resource=obj
            ).first()
            return rating.rating if rating else None
        return None

    def get_comments_count(self, obj) -> int:
        annotated = getattr(obj, "comments_count", None)
        if annotated is not None:
            return annotated
        return obj.comments.count()

    def get_ratings_count(self, obj) -> int:
        annotated = getattr(obj, "ratings_count", None)
        if annotated is not None:
            return annotated
        return obj.ratings.count()


class ResourceSerializer(serializers.ModelSerializer):
    """Serializer for Resource model."""

    uploaded_by_details = UserSerializer(source="uploaded_by", read_only=True)
    tags_list = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()
    additional_files = ResourceFileSerializer(many=True, read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    can_share = serializers.SerializerMethodField()
    auto_rating = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            "file",
            "file_url",
            "thumbnail",
            "thumbnail_url",
            "file_size",
            "file_type",
            "file_icon",
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "tags",
            "tags_list",
            "uploaded_by",
            "uploaded_by_details",
            "status",
            "is_public",
            "is_pinned",
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "auto_rating",
            "additional_files",
            "is_bookmarked",
            "is_favorited",
            "user_rating",
            "can_share",
            "ocr_text",
            "ai_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "file_size",
            "file_type",
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "created_at",
            "updated_at",
        ]

    def get_tags_list(self, obj) -> list[str]:
        return obj.get_tags_list()

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_thumbnail_url(self, obj) -> str | None:
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()

    def get_is_bookmarked(self, obj) -> bool:
        annotated = getattr(obj, "is_bookmarked", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.bookmarks.models import Bookmark

            return Bookmark.objects.filter(user=request.user, resource=obj).exists()
        return False

    def get_user_rating(self, obj) -> int | None:
        annotated = getattr(obj, "user_rating", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.ratings.models import Rating

            rating = Rating.objects.filter(user=request.user, resource=obj).first()
            return rating.value if rating else None
        return None

    def get_is_favorited(self, obj) -> bool:
        annotated = getattr(obj, "is_favorited", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.favorites.models import Favorite, FavoriteType

            return Favorite.objects.filter(
                user=request.user,
                favorite_type=FavoriteType.RESOURCE,
                resource=obj,
            ).exists()
        return False

    def get_can_share(self, obj) -> bool:
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        can_share, _ = ResourceShareService.can_share(obj, user)
        return can_share

    def get_auto_rating(self, obj) -> float:
        likes_count = getattr(obj, "likes_count", None)
        ratings_count = getattr(obj, "ratings_count", None)
        if likes_count is None:
            try:
                from apps.favorites.models import Favorite, FavoriteType

                likes_count = Favorite.objects.filter(
                    resource=obj,
                    favorite_type=FavoriteType.RESOURCE,
                ).count()
            except Exception:
                likes_count = 0
        return calculate_auto_rating(
            obj,
            ratings_count=ratings_count,
            likes_count=likes_count,
        )


class CourseProgressSerializer(serializers.ModelSerializer):
    """Serializer for per-resource progress records."""

    course_name = serializers.CharField(source="course.name", read_only=True)
    resource_title = serializers.CharField(source="resource.title", read_only=True)

    class Meta:
        model = CourseProgress
        fields = [
            "id",
            "course",
            "course_name",
            "resource",
            "resource_title",
            "status",
            "completion_percentage",
            "time_spent_minutes",
            "last_accessed",
            "completed_at",
        ]


class ResourceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for resource listing."""

    uploaded_by_name = serializers.CharField(
        source="uploaded_by.full_name", read_only=True
    )
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    can_share = serializers.SerializerMethodField()
    auto_rating = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            "file_url",
            "thumbnail_url",
            "file_icon",
            "file_size",
            "file_type",
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "tags",
            "uploaded_by_name",
            "status",
            "is_pinned",
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "auto_rating",
            "comments_count",
            "ratings_count",
            "is_bookmarked",
            "is_favorited",
            "can_share",
            "created_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_thumbnail_url(self, obj) -> str | None:
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()

    def get_comments_count(self, obj) -> int:
        annotated = getattr(obj, "comments_count", None)
        if annotated is not None:
            return annotated
        return obj.comments.count()

    def get_ratings_count(self, obj) -> int:
        annotated = getattr(obj, "ratings_count", None)
        if annotated is not None:
            return annotated
        return obj.ratings.count()

    def get_is_bookmarked(self, obj) -> bool:
        annotated = getattr(obj, "is_bookmarked", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.bookmarks.models import Bookmark

            return Bookmark.objects.filter(user=request.user, resource=obj).exists()
        return False

    def get_is_favorited(self, obj) -> bool:
        annotated = getattr(obj, "is_favorited", None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.favorites.models import Favorite, FavoriteType

            return Favorite.objects.filter(
                user=request.user,
                favorite_type=FavoriteType.RESOURCE,
                resource=obj,
            ).exists()
        return False

    def get_can_share(self, obj) -> bool:
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        can_share, _ = ResourceShareService.can_share(obj, user)
        return can_share

    def get_auto_rating(self, obj) -> float:
        likes_count = getattr(obj, "likes_count", None)
        ratings_count = getattr(obj, "ratings_count", None)
        if likes_count is None:
            try:
                from apps.favorites.models import Favorite, FavoriteType

                likes_count = Favorite.objects.filter(
                    resource=obj,
                    favorite_type=FavoriteType.RESOURCE,
                ).count()
            except Exception:
                likes_count = 0
        return calculate_auto_rating(
            obj,
            ratings_count=ratings_count,
            likes_count=likes_count,
        )


class ResourceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating resources."""

    additional_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",
            "resource_type",
            "file",
            "thumbnail",
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "tags",
            "is_public",
            "additional_files",
        ]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        additional_files = validated_data.pop("additional_files", [])
        is_mobile = self.context.get("is_mobile", False)
        resource = ResourceUploadService.create_resource_upload(
            user=self.context["request"].user,
            validated_data=validated_data,
            is_mobile=is_mobile,
        )

        # Create additional files
        for file in additional_files:
            ResourceFile.objects.create(resource=resource, file=file)

        return resource

    def validate(self, attrs):
        file_obj = attrs.get("file")
        title = attrs.get("title")
        if not title and file_obj:
            attrs["title"] = (
                sanitize_filename(file_obj.name)
                .rsplit(".", 1)[0]
                .replace("_", " ")
                .strip()
                .title()
            )
        is_mobile = self.context.get("is_mobile", False)
        ResourceUploadService.validate_resource_upload(
            user=self.context["request"].user,
            data=attrs,
            file_obj=file_obj,
            is_mobile=is_mobile,
        )
        return attrs


class ResourceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating resources."""

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",
            "resource_type",
            "thumbnail",
            "file",
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "tags",
            "is_public",
            "is_pinned",
        ]

    def validate(self, attrs):
        ResourceUploadService.validate_resource_upload(
            user=self.context["request"].user,
            data={
                **{
                    "title": self.instance.title,
                    "tags": self.instance.tags,
                    "faculty": self.instance.faculty,
                    "department": self.instance.department,
                    "course": self.instance.course,
                    "unit": self.instance.unit,
                    "semester": self.instance.semester,
                    "year_of_study": self.instance.year_of_study,
                },
                **attrs,
            },
            file_obj=attrs.get("file"),
            instance=self.instance,
        )
        return attrs

    def update(self, instance, validated_data):
        return ResourceUploadService.update_resource_upload(
            instance=instance,
            user=self.context["request"].user,
            validated_data=validated_data,
        )


class MyUploadListSerializer(serializers.ModelSerializer):
    """Serializer for listing current user's uploads."""

    file_url = serializers.SerializerMethodField()
    rejection_reason = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "resource_type",
            "status",
            "file_url",
            "file_size",
            "file_type",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_rejection_reason(self, obj) -> str:
        request = self.context.get("request")
        user = request.user if request else None
        if obj.status != "rejected":
            return ""
        if user and (
            obj.uploaded_by_id == user.id or user.is_admin or user.is_moderator
        ):
            return obj.rejection_reason
        return ""


class FolderSerializer(serializers.ModelSerializer):
    """Serializer for Folder model."""

    items_count = serializers.SerializerMethodField()
    subfolders_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "color",
            "is_pinned",
            "parent",
            "items_count",
            "subfolders_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_items_count(self, obj) -> int:
        return obj.items.count()

    def get_subfolders_count(self, obj) -> int:
        return obj.subfolders.count()


class FolderItemSerializer(serializers.ModelSerializer):
    """Serializer for FolderItem model."""

    resource_details = ResourceListSerializer(source="resource", read_only=True)

    class Meta:
        model = FolderItem
        fields = ["id", "folder", "resource", "resource_details", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserStorageSerializer(serializers.ModelSerializer):
    """Serializer for UserStorage model."""

    usage_percentage = serializers.SerializerMethodField()
    usage_mb = serializers.SerializerMethodField()
    limit_mb = serializers.SerializerMethodField()

    class Meta:
        model = UserStorage
        fields = [
            "used_storage",
            "storage_limit",
            "usage_percentage",
            "usage_mb",
            "limit_mb",
            "created_at",
            "updated_at",
        ]

    def get_usage_percentage(self, obj) -> float:
        return obj.get_usage_percentage()

    def get_usage_mb(self, obj) -> float:
        return obj.used_storage / (1024 * 1024)

    def get_limit_mb(self, obj) -> float:
        return obj.storage_limit / (1024 * 1024)


class TrendingResourceSerializer(serializers.ModelSerializer):
    """Serializer for trending resources."""

    uploaded_by_name = serializers.CharField(
        source="uploaded_by.full_name", read_only=True
    )
    file_icon = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "thumbnail",
            "file_icon",
            "resource_type",
            "download_count",
            "view_count",
            "average_rating",
            "uploaded_by_name",
        ]

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()


class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions."""

    resource_ids = serializers.ListField(child=serializers.UUIDField(), required=True)
    action = serializers.ChoiceField(
        choices=["delete", "approve", "reject", "pin", "unpin"], required=True
    )


class PersonalFolderSerializer(serializers.ModelSerializer):
    """Serializer for PersonalFolder model."""

    file_count = serializers.SerializerMethodField()
    total_size = serializers.SerializerMethodField()
    subfolders_count = serializers.SerializerMethodField()

    class Meta:
        model = PersonalFolder
        fields = [
            "id",
            "name",
            "slug",
            "color",
            "is_favorite",
            "parent",
            "file_count",
            "total_size",
            "subfolders_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_file_count(self, obj) -> int:
        return obj.get_file_count()

    def get_total_size(self, obj) -> int:
        return obj.get_total_size()

    def get_subfolders_count(self, obj) -> int:
        return obj.subfolders.count()


class PersonalFolderDetailSerializer(PersonalFolderSerializer):
    """Detailed serializer for PersonalFolder with subfolders and files."""

    subfolders = PersonalFolderSerializer(many=True, read_only=True)
    files = serializers.SerializerMethodField()

    class Meta(PersonalFolderSerializer.Meta):
        fields = PersonalFolderSerializer.Meta.fields + ["subfolders", "files"]

    def get_files(self, obj) -> list[dict]:
        files = obj.personal_resources.all()
        return PersonalResourceListSerializer(files, many=True).data


class PersonalResourceSerializer(serializers.ModelSerializer):
    """Serializer for PersonalResource model."""

    file_url = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    linked_resource_title = serializers.SerializerMethodField()

    class Meta:
        model = PersonalResource
        fields = [
            "id",
            "folder",
            "title",
            "file",
            "file_url",
            "file_icon",
            "file_type",
            "file_size",
            "description",
            "tags",
            "tags_list",
            "visibility",
            "source_type",
            "is_favorite",
            "last_accessed_at",
            "linked_public_resource",
            "linked_resource_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "file_type", "file_size", "created_at", "updated_at"]

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()

    def get_tags_list(self, obj) -> list[str]:
        return obj.get_tags_list()

    def get_linked_resource_title(self, obj) -> str | None:
        if obj.linked_public_resource:
            return obj.linked_public_resource.title
        return None


class PersonalResourceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for PersonalResource list views."""

    file_url = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()

    class Meta:
        model = PersonalResource
        fields = [
            "id",
            "title",
            "file_url",
            "file_type",
            "file_size",
            "is_favorite",
            "last_accessed_at",
            "file_icon",
            "created_at",
        ]

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()


class FolderTreeSerializer(serializers.ModelSerializer):
    """Serializer for folder tree structure."""

    children = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    subfolder_count = serializers.SerializerMethodField()

    class Meta:
        model = PersonalFolder
        fields = [
            "id",
            "name",
            "slug",
            "color",
            "is_favorite",
            "children",
            "file_count",
            "subfolder_count",
        ]

    def get_children(self, obj) -> list[dict]:
        # Get direct children
        children = obj.subfolders.all()
        return FolderTreeSerializer(children, many=True).data

    def get_file_count(self, obj) -> int:
        return obj.personal_resources.count()

    def get_subfolder_count(self, obj) -> int:
        return obj.subfolders.count()


class FolderContentsSerializer(serializers.ModelSerializer):
    """Serializer for folder contents (files and subfolders)."""

    subfolders = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()

    class Meta:
        model = PersonalFolder
        fields = [
            "id",
            "name",
            "slug",
            "color",
            "is_favorite",
            "subfolders",
            "files",
            "breadcrumbs",
        ]

    def get_subfolders(self, obj) -> list[dict]:
        subfolders = obj.subfolders.all()
        return PersonalFolderSerializer(subfolders, many=True).data

    def get_files(self, obj) -> list[dict]:
        files = obj.personal_resources.all()
        return PersonalResourceListSerializer(
            files, many=True, context=self.context
        ).data

    def get_breadcrumbs(self, obj) -> list[dict]:
        return obj.get_breadcrumbs()


class FolderMoveSerializer(serializers.Serializer):
    """Serializer for moving folders."""

    parent_id = serializers.UUIDField(required=False, allow_null=True)


class SaveToLibrarySerializer(serializers.Serializer):
    """Serializer for saving public resource to personal library."""

    folder_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(required=False, max_length=500)


class RelatedResourceSerializer(serializers.ModelSerializer):
    """Serializer for related resources."""

    uploaded_by_name = serializers.CharField(
        source="uploaded_by.full_name", read_only=True
    )
    file_icon = serializers.SerializerMethodField()
    relevance_score = serializers.SerializerMethodField()
    auto_rating = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "thumbnail",
            "file_icon",
            "resource_type",
            "file_type",
            "download_count",
            "share_count",
            "view_count",
            "average_rating",
            "auto_rating",
            "uploaded_by_name",
            "relevance_score",
            "created_at",
        ]

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()

    def get_relevance_score(self, obj) -> float:
        return getattr(obj, "relevance_score", 0)

    def get_auto_rating(self, obj) -> float:
        likes_count = getattr(obj, "likes_count", None)
        ratings_count = getattr(obj, "ratings_count", None)
        if likes_count is None:
            try:
                from apps.favorites.models import Favorite, FavoriteType

                likes_count = Favorite.objects.filter(
                    resource=obj,
                    favorite_type=FavoriteType.RESOURCE,
                ).count()
            except Exception:
                likes_count = 0
        return calculate_auto_rating(
            obj,
            ratings_count=ratings_count,
            likes_count=likes_count,
        )


class ResourceDetailSerializer(serializers.ModelSerializer):
    """Enhanced serializer for resource detail page."""

    uploaded_by_details = UserSerializer(source="uploaded_by", read_only=True)
    tags_list = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    file_icon = serializers.SerializerMethodField()
    additional_files = ResourceFileSerializer(many=True, read_only=True)

    # User-specific data
    is_bookmarked = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    is_in_my_library = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_download = serializers.SerializerMethodField()
    can_share = serializers.SerializerMethodField()

    # Engagement data
    comments_count = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    auto_rating = serializers.SerializerMethodField()

    # Related resources
    related_resources = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            # Core data
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            "file",
            "file_url",
            "thumbnail",
            "thumbnail_url",
            "file_size",
            "file_type",
            "file_icon",
            # Academic metadata
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "tags",
            "tags_list",
            # Upload info
            "uploaded_by",
            "uploaded_by_details",
            # Status
            "status",
            "is_public",
            "is_pinned",
            # Engagement
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "auto_rating",
            "comments_count",
            "ratings_count",
            # User-specific
            "is_bookmarked",
            "is_favorited",
            "is_in_my_library",
            "user_rating",
            "can_edit",
            "can_delete",
            "can_download",
            "can_share",
            # Additional
            "additional_files",
            "related_resources",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "file_size",
            "file_type",
            "view_count",
            "download_count",
            "share_count",
            "average_rating",
            "created_at",
            "updated_at",
        ]

    def get_tags_list(self, obj) -> list[str]:
        return obj.get_tags_list()

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None

    def get_thumbnail_url(self, obj) -> str | None:
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_file_icon(self, obj) -> str:
        return obj.get_file_icon()

    def get_is_bookmarked(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.bookmarks.models import Bookmark

            return Bookmark.objects.filter(user=request.user, resource=obj).exists()
        return False

    def get_is_favorited(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.favorites.models import Favorite, FavoriteType

            return Favorite.objects.filter(
                user=request.user,
                favorite_type=FavoriteType.RESOURCE,
                resource=obj,
            ).exists()
        return False

    def get_is_in_my_library(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.resources.models import FolderItem

            return FolderItem.objects.filter(
                folder__user=request.user, resource=obj
            ).exists()
        return False

    def get_user_rating(self, obj) -> int | None:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from apps.ratings.models import Rating

            rating = Rating.objects.filter(user=request.user, resource=obj).first()
            return rating.value if rating else None
        return None

    def get_can_edit(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return (
                obj.uploaded_by == request.user
                or request.user.is_admin
                or request.user.is_moderator
            )
        return False

    def get_can_delete(self, obj) -> bool:
        return self.get_can_edit(obj)

    def get_can_download(self, obj) -> bool:
        request = self.context.get("request")
        if obj.status != "approved":
            if request and request.user.is_authenticated:
                return (
                    obj.uploaded_by == request.user
                    or request.user.is_admin
                    or request.user.is_moderator
                )
            return False
        return True

    def get_can_share(self, obj) -> bool:
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        can_share, _ = ResourceShareService.can_share(obj, user)
        return can_share

    def get_comments_count(self, obj) -> int:
        return obj.comments.count()

    def get_ratings_count(self, obj) -> int:
        return obj.ratings.count()

    def get_auto_rating(self, obj) -> float:
        likes_count = getattr(obj, "likes_count", None)
        ratings_count = getattr(obj, "ratings_count", None)
        if likes_count is None:
            try:
                from apps.favorites.models import Favorite, FavoriteType

                likes_count = Favorite.objects.filter(
                    resource=obj,
                    favorite_type=FavoriteType.RESOURCE,
                ).count()
            except Exception:
                likes_count = 0
        return calculate_auto_rating(
            obj,
            ratings_count=ratings_count,
            likes_count=likes_count,
        )

    def get_related_resources(self, obj) -> list[dict]:
        request = self.context.get("request")
        user = request.user if request else None

        from apps.resources.services import ResourceDetailService

        service = ResourceDetailService(obj, user)
        related = service.get_related_resources(limit=5)

        return RelatedResourceSerializer(related, many=True, context=self.context).data


class ResourceActionSerializer(serializers.Serializer):
    """Serializer for resource actions like rating, reporting."""

    value = serializers.IntegerField(required=False, min_value=1, max_value=5)
    reason = serializers.CharField(required=False, max_length=50)
    message = serializers.CharField(required=False, max_length=1000)


class ResourceShareLinkSerializer(serializers.Serializer):
    """Serializer for resource sharing payload."""

    resource_id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    share_url = serializers.URLField(read_only=True, allow_blank=True)
    deep_link_url = serializers.CharField(read_only=True)
    share_message = serializers.CharField(read_only=True, allow_blank=True)
    metadata_summary = serializers.CharField(read_only=True, allow_blank=True)
    can_share = serializers.BooleanField(read_only=True)
    reason = serializers.CharField(read_only=True, allow_blank=True, required=False)


class ResourceShareTrackSerializer(serializers.Serializer):
    """Serializer for recording resource share action."""

    share_method = serializers.ChoiceField(
        choices=ResourceShareEvent.ShareMethod.choices,
        required=False,
        default=ResourceShareEvent.ShareMethod.OTHER,
    )


class ShareToStudentSerializer(serializers.Serializer):
    """Serializer for sharing a resource to a student."""

    student_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ShareToStudyGroupSerializer(serializers.Serializer):
    """Serializer for sharing a resource to a study group."""

    group_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ShareResultSerializer(serializers.Serializer):
    """Serializer for share result."""

    success = serializers.BooleanField()
    message = serializers.CharField()
    resource_id = serializers.CharField()
    shared_with = serializers.ListField(required=False)


class ResourceRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating resource requests."""

    class Meta:
        model = ResourceRequest
        fields = ['title', 'description', 'course', 'faculty', 'department', 'priority']


class ResourceRequestSerializer(serializers.ModelSerializer):
    """Serializer for resource requests."""

    requested_by = UserSerializer(read_only=True)
    course_name = serializers.SerializerMethodField()
    is_upvoted = serializers.SerializerMethodField()

    class Meta:
        model = ResourceRequest
        fields = [
            'id', 'title', 'description', 'course', 'course_name',
            'faculty', 'department', 'status', 'priority', 'upvotes',
            'requested_by', 'is_upvoted', 'fulfilled_by', 'fulfilled_resource',
            'created_at', 'updated_at'
        ]
        ref_name = "ResourceRequestItem"

    def get_course_name(self, obj) -> str | None:
        return obj.course.name if obj.course else None

    def get_is_upvoted(self, obj) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user in obj.requested_by_upvoted.all()
        return False


class StorageUpgradeRequestSerializer(serializers.ModelSerializer):
    """Serializer for storage upgrade requests."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = StorageUpgradeRequest
        fields = [
            "id",
            "user",
            "plan",
            "billing_cycle",
            "payment_method",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]


class StorageUpgradeRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating storage upgrade requests."""

    class Meta:
        model = StorageUpgradeRequest
        fields = ["plan", "billing_cycle", "payment_method", "notes"]
