"""
Serializers for study group social features.
"""

from rest_framework import serializers

from apps.courses.models import Course
from apps.faculties.models import Department, Faculty

from .models import StudyGroup, StudyGroupMember, StudyGroupPost, StudyGroupPostComment, StudyGroupPostLike, StudyGroupResource, StudyGroupInviteLink


class StudyGroupUserSerializer(serializers.Serializer):
    """Compact user representation for study group responses."""

    id = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj) -> str | None:
        if getattr(obj, "profile_image", None):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
        return None


class StudyGroupCourseSerializer(serializers.Serializer):
    """Compact course representation."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)


class StudyGroupListSerializer(serializers.ModelSerializer):
    """Serializer for study group listings and details."""

    course = StudyGroupCourseSerializer(read_only=True)
    created_by = StudyGroupUserSerializer(source="creator", read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    is_member = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    is_private = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "description",
            "course",
            "year_of_study",
            "is_public",
            "is_private",
            "max_members",
            "member_count",
            "status",
            "created_by",
            "created_at",
            "is_member",
            "my_role",
        ]

    def get_is_member(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if obj.creator_id == user.id:
            return True
        return obj.memberships.filter(user=user, status="active").exists()

    def get_my_role(self, obj) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        if obj.creator_id == user.id:
            membership = obj.memberships.filter(user=user).only("role").first()
            return membership.role if membership else "admin"
        membership = obj.memberships.filter(user=user, status="active").only("role").first()
        return membership.role if membership else None

    def get_is_private(self, obj) -> bool:
        return not obj.is_public


class StudyGroupCreateSerializer(serializers.Serializer):
    """Serializer for study group creation."""

    name = serializers.CharField(max_length=255)
    description = serializers.CharField()
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.filter(is_active=True),
        source="course",
        required=False,
        allow_null=True,
    )
    faculty_id = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.filter(is_active=True),
        source="faculty",
        required=False,
        allow_null=True,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True),
        source="department",
        required=False,
        allow_null=True,
    )
    year_of_study = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    is_public = serializers.BooleanField(required=False, default=True)
    max_members = serializers.IntegerField(required=False, default=10, min_value=2, max_value=500)

    def validate(self, attrs):
        faculty = attrs.get("faculty")
        department = attrs.get("department")
        course = attrs.get("course")

        if department and faculty and department.faculty_id != faculty.id:
            raise serializers.ValidationError(
                {"department_id": "Department must belong to the selected faculty."}
            )
        if course and department and course.department_id != department.id:
            raise serializers.ValidationError(
                {"course_id": "Course must belong to the selected department."}
            )
        if course and faculty and course.department.faculty_id != faculty.id:
            raise serializers.ValidationError(
                {"course_id": "Course must belong to the selected faculty."}
            )
        return attrs


class StudyGroupUpdateSerializer(serializers.ModelSerializer):
    """Serializer for study group updates - only editable fields."""

    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.filter(is_active=True),
        source="course",
        required=False,
        allow_null=True,
    )
    faculty_id = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.filter(is_active=True),
        source="faculty",
        required=False,
        allow_null=True,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True),
        source="department",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = StudyGroup
        fields = [
            "name",
            "description",
            "course_id",
            "faculty_id",
            "department_id",
            "year_of_study",
            "is_public",
            "max_members",
        ]

    def validate(self, attrs):
        faculty = attrs.get("faculty")
        department = attrs.get("department")
        course = attrs.get("course")

        if department and faculty and department.faculty_id != faculty.id:
            raise serializers.ValidationError(
                {"department_id": "Department must belong to the selected faculty."}
            )
        if course and department and course.department_id != department.id:
            raise serializers.ValidationError(
                {"course_id": "Course must belong to the selected department."}
            )
        if course and faculty and course.department.faculty_id != faculty.id:
            raise serializers.ValidationError(
                {"course_id": "Course must belong to the selected faculty."}
            )
        return attrs


class StudyGroupMemberSerializer(serializers.ModelSerializer):
    """Serializer for study group membership entries."""

    user = StudyGroupUserSerializer(read_only=True)

    class Meta:
        model = StudyGroupMember
        fields = ["id", "user", "role", "status", "joined_at"]


class StudyGroupPostSerializer(serializers.ModelSerializer):
    """Serializer for study group posts."""

    author = StudyGroupUserSerializer(read_only=True)

    class Meta:
        model = StudyGroupPost
        fields = [
            "id",
            "title",
            "content",
            "author",
            "is_pinned",
            "is_announcement",
            "likes_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]


class StudyGroupPostCreateSerializer(serializers.Serializer):
    """Serializer for study group post creation."""

    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    content = serializers.CharField()


class StudyGroupPostCommentSerializer(serializers.ModelSerializer):
    """Serializer for study group post comments."""

    author = StudyGroupUserSerializer(read_only=True)

    class Meta:
        model = StudyGroupPostComment
        fields = [
            "id",
            "post",
            "author",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class StudyGroupPostLikeSerializer(serializers.ModelSerializer):
    """Serializer for study group post likes."""

    class Meta:
        model = StudyGroupPostLike
        fields = ["id", "post", "user", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class StudyGroupResourceSerializer(serializers.ModelSerializer):
    """Serializer for resources shared in a study group."""

    id = serializers.UUIDField(source="resource_id", read_only=True)
    title = serializers.CharField(source="resource.title", read_only=True)
    resource_type = serializers.CharField(source="resource.resource_type", read_only=True)
    uploaded_by = StudyGroupUserSerializer(source="resource.uploaded_by", read_only=True)

    class Meta:
        model = StudyGroupResource
        fields = ["id", "title", "resource_type", "uploaded_by", "created_at"]


class CreateStudyGroupResourceSerializer(serializers.Serializer):
    """Serializer for sharing a resource in a study group."""

    resource_id = serializers.UUIDField()
    description = serializers.CharField(required=False, allow_blank=True)


class CreateInviteLinkSerializer(serializers.Serializer):
    """Serializer for creating an invite link."""

    expires_in_hours = serializers.IntegerField(required=False, min_value=1, max_value=168)
    allow_auto_join = serializers.BooleanField(default=True)
    max_uses = serializers.IntegerField(required=False, min_value=1, max_value=1000)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class InviteLinkSerializer(serializers.ModelSerializer):
    """Serializer for invite link responses."""

    invite_link = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudyGroupInviteLink
        fields = [
            "id",
            "token",
            "invite_link",
            "is_active",
            "expires_at",
            "max_uses",
            "use_count",
            "allow_auto_join",
            "notes",
            "created_by_name",
            "created_at",
            "is_expired",
            "is_valid",
        ]

    def get_invite_link(self, obj) -> str:
        from .invite_services import StudyGroupInviteService
        request = self.context.get("request")
        return StudyGroupInviteService.build_invite_url(obj.token, request=request)


class InviteLinkValidateSerializer(serializers.Serializer):
    """Serializer for invite link validation response."""

    valid = serializers.BooleanField()
    group = serializers.DictField()
    already_member = serializers.BooleanField()
    can_join_directly = serializers.BooleanField()
    message = serializers.CharField()
