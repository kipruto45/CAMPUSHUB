"""Serializers for admin management module."""

from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import ProfileSerializer
from apps.admin_management.models import (
    AdminInvitationBatch,
    AdminInvitationRole,
    AdminRoleInvitation,
)
from apps.admin_management.services import (
    actor_can_invite_role,
    build_role_invitation_landing_url,
)
from apps.announcements.models import Announcement
from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty
from apps.reports.models import Report
from apps.resources.models import Resource
from apps.social.models import StudyGroup


def _user_display_name(user):
    """Return a robust display name for a user."""
    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    combined = f"{first_name} {last_name}".strip()
    if combined:
        return combined
    full_name = getattr(user, "full_name", "") or ""
    if full_name:
        return full_name
    return getattr(user, "email", "")


class AdminUserListSerializer(serializers.ModelSerializer):
    """Compact serializer for admin user listings."""

    full_name = serializers.SerializerMethodField()
    uploads_count = serializers.IntegerField(read_only=True)
    reports_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "registration_number",
            "role",
            "is_active",
            "is_verified",
            "date_joined",
            "last_login",
            "uploads_count",
            "reports_count",
        ]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return _user_display_name(obj)


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for admin user management."""

    full_name = serializers.SerializerMethodField()
    profile = ProfileSerializer(read_only=True)
    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "registration_number",
            "phone_number",
            "profile_image",
            "faculty",
            "faculty_name",
            "department",
            "department_name",
            "course",
            "course_name",
            "year_of_study",
            "semester",
            "role",
            "is_verified",
            "is_active",
            "date_joined",
            "last_login",
            "profile",
            "stats",
        ]
        read_only_fields = ["id", "email", "date_joined", "last_login", "profile"]

    def get_full_name(self, obj) -> str:
        return _user_display_name(obj)

    def get_stats(self, obj) -> dict:
        profile = getattr(obj, "profile", None)
        return {
            "total_uploads": getattr(profile, "total_uploads", 0) or 0,
            "total_downloads": getattr(profile, "total_downloads", 0) or 0,
            "total_bookmarks": getattr(profile, "total_bookmarks", 0) or 0,
            "total_comments": getattr(profile, "total_comments", 0) or 0,
            "total_ratings": getattr(profile, "total_ratings", 0) or 0,
        }


class AdminUserStatusUpdateSerializer(serializers.Serializer):
    """Payload for activating/deactivating users."""

    is_active = serializers.BooleanField()


class AdminUserRoleUpdateSerializer(serializers.Serializer):
    """Payload for role updates."""

    role = serializers.ChoiceField(choices=[choice[0] for choice in User.ROLE_CHOICES])

    def validate_role(self, value):
        return str(value).upper()


class AdminInvitationRoleSerializer(serializers.ModelSerializer):
    """Serializer for invitable role definitions."""

    can_invite = serializers.SerializerMethodField()

    class Meta:
        model = AdminInvitationRole
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "is_assignable",
            "sort_order",
            "requires_superuser",
            "inviter_permissions",
            "permission_preset",
            "email_subject_template",
            "email_body_template",
            "metadata",
            "can_invite",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_can_invite(self, obj) -> bool:
        request = self.context.get("request")
        actor = request.user if request and getattr(request, "user", None) else None
        return actor_can_invite_role(actor, obj)


class AdminInvitationBatchSerializer(serializers.ModelSerializer):
    """Serializer for bulk invitation batches."""

    invited_by_name = serializers.SerializerMethodField()
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = AdminInvitationBatch
        fields = [
            "id",
            "name",
            "source_file_name",
            "invited_by",
            "invited_by_name",
            "total_rows",
            "successful_rows",
            "failed_rows",
            "success_rate",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_invited_by_name(self, obj) -> str:
        return _user_display_name(obj.invited_by)


class AdminRoleInvitationSerializer(serializers.ModelSerializer):
    """Serializer for admin-managed role invitations."""

    invited_by_name = serializers.SerializerMethodField()
    accepted_by_name = serializers.SerializerMethodField()
    revoked_by_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    has_existing_account = serializers.SerializerMethodField()
    accept_url = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    role_details = serializers.SerializerMethodField()
    batch = AdminInvitationBatchSerializer(read_only=True)

    class Meta:
        model = AdminRoleInvitation
        fields = [
            "id",
            "email",
            "role",
            "roles",
            "role_details",
            "note",
            "status",
            "source",
            "metadata",
            "accepted_metadata",
            "email_subject",
            "email_body",
            "invited_by",
            "invited_by_name",
            "accepted_by",
            "accepted_by_name",
            "revoked_by",
            "revoked_by_name",
            "batch",
            "has_existing_account",
            "accept_url",
            "expires_at",
            "last_sent_at",
            "accepted_at",
            "revoked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_invited_by_name(self, obj) -> str:
        return _user_display_name(obj.invited_by)

    def get_accepted_by_name(self, obj) -> str:
        return _user_display_name(obj.accepted_by)

    def get_revoked_by_name(self, obj) -> str:
        return _user_display_name(obj.revoked_by)

    def get_has_existing_account(self, obj) -> bool:
        return User.objects.filter(email__iexact=obj.email).exists()

    def get_accept_url(self, obj) -> str:
        return build_role_invitation_landing_url(self.context.get("request"), obj.token)

    def get_roles(self, obj) -> list[str]:
        return obj.get_role_codes()

    def get_role_details(self, obj) -> list[dict]:
        details = []
        for role_assignment in obj.get_role_assignments():
            if not role_assignment.role_definition_id:
                continue
            details.append(
                {
                    "code": role_assignment.role_definition.code,
                    "name": role_assignment.role_definition.name,
                    "description": role_assignment.role_definition.description,
                    "is_primary": role_assignment.is_primary,
                    "permission_preset": role_assignment.permission_preset,
                }
            )
        if details:
            return details
        return [
            {
                "code": obj.role,
                "name": obj.get_role_display(),
                "description": "",
                "is_primary": True,
                "permission_preset": [],
            }
        ]


class AdminRoleInvitationCreateSerializer(serializers.Serializer):
    """Payload for creating a role invitation."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[choice[0] for choice in User.ROLE_CHOICES],
        required=False,
    )
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in User.ROLE_CHOICES]),
        required=False,
        allow_empty=False,
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    metadata = serializers.JSONField(required=False)
    email_subject = serializers.CharField(required=False, allow_blank=True, max_length=255)
    email_body = serializers.CharField(required=False, allow_blank=True)
    expires_in_days = serializers.IntegerField(required=False, min_value=1, max_value=30, default=7)

    def validate_email(self, value):
        return str(value or "").strip().lower()

    def validate_role(self, value):
        return str(value or "").strip().upper()

    def validate_roles(self, values):
        normalized_values = []
        for value in values:
            normalized_value = str(value or "").strip().upper()
            if normalized_value not in normalized_values:
                normalized_values.append(normalized_value)
        return normalized_values

    def validate(self, attrs):
        selected_roles = attrs.get("roles") or ([attrs["role"]] if attrs.get("role") else [])
        if not selected_roles:
            raise serializers.ValidationError({"roles": "Select at least one role."})

        role_definitions = {
            role_definition.code: role_definition
            for role_definition in AdminInvitationRole.objects.filter(
                code__in=selected_roles,
                is_active=True,
                is_assignable=True,
            )
        }
        missing_roles = [role for role in selected_roles if role not in role_definitions]
        if missing_roles:
            raise serializers.ValidationError(
                {"roles": f"Unknown or inactive roles: {', '.join(missing_roles)}."}
            )

        request = self.context.get("request")
        actor = request.user if request and getattr(request, "user", None) else None
        forbidden_roles = [
            role_definition.name
            for role_definition in role_definitions.values()
            if not actor_can_invite_role(actor, role_definition)
        ]
        if forbidden_roles:
            raise serializers.ValidationError(
                {
                    "roles": (
                        "You do not have permission to invite: "
                        + ", ".join(sorted(forbidden_roles))
                        + "."
                    )
                }
            )

        attrs["roles"] = selected_roles
        existing_user = User.objects.filter(email__iexact=attrs["email"]).first()
        existing_role_codes = set(
            getattr(existing_user, "assigned_role_codes", []) if existing_user else []
        )
        if existing_user and set(selected_roles).issubset(existing_role_codes):
            raise serializers.ValidationError(
                {"email": "This user already has the selected role assignments."}
            )
        return attrs


class AdminRoleInvitationBulkCreateSerializer(serializers.Serializer):
    """Payload for CSV-based bulk invitation uploads."""

    csv_file = serializers.FileField(required=False)
    csv_text = serializers.CharField(required=False, allow_blank=True)
    default_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in User.ROLE_CHOICES]),
        required=False,
        allow_empty=False,
    )
    default_note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    default_expires_in_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=30,
        default=7,
    )

    def validate_default_roles(self, values):
        normalized_values = []
        for value in values:
            normalized_value = str(value or "").strip().upper()
            if normalized_value not in normalized_values:
                normalized_values.append(normalized_value)
        return normalized_values

    def validate(self, attrs):
        csv_file = attrs.get("csv_file")
        csv_text = str(attrs.get("csv_text") or "").strip()
        if not csv_file and not csv_text:
            raise serializers.ValidationError(
                {"csv_file": "Provide either a CSV file or CSV text content."}
            )
        return attrs


class AdminRoleInvitationAcceptSerializer(serializers.Serializer):
    """Payload for accepting a role invitation."""

    token = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    password_confirm = serializers.CharField(required=False, allow_blank=True, write_only=True)
    registration_number = serializers.CharField(required=False, allow_blank=True, max_length=100)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        password = attrs.get("password", "")
        password_confirm = attrs.pop("password_confirm", "")
        if password or password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError(
                    {"password_confirm": "Passwords do not match."}
                )
        return attrs


class AdminResourceSerializer(serializers.ModelSerializer):
    """Serializer for admin resource management."""

    uploaded_by_name = serializers.SerializerMethodField()
    course_name = serializers.CharField(source="course.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    reports_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            "status",
            "rejection_reason",
            "average_rating",
            "file_type",
            "file_url",
            "file_size",
            "uploaded_by",
            "uploaded_by_name",
            "course",
            "course_name",
            "unit",
            "unit_name",
            "download_count",
            "view_count",
            "is_pinned",
            "reports_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "uploaded_by",
            "uploaded_by_name",
            "download_count",
            "view_count",
            "reports_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]

    def get_uploaded_by_name(self, obj) -> str:
        if not obj.uploaded_by:
            return ""
        return _user_display_name(obj.uploaded_by)

    def get_reports_count(self, obj) -> int:
        if hasattr(obj, "report_items_count"):
            return int(obj.report_items_count or 0)
        return obj.reports.count()

    def get_comments_count(self, obj) -> int:
        if hasattr(obj, "comments_total"):
            return int(obj.comments_total or 0)
        return obj.comments.count()

    def get_file_url(self, obj) -> str | None:
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class AdminResourceReviewSerializer(serializers.Serializer):
    """Payload for resource moderation actions."""

    reason = serializers.CharField(required=False, allow_blank=True)


class AdminResourceRejectSerializer(serializers.Serializer):
    """Payload for resource rejection action."""

    reason = serializers.CharField(required=True, allow_blank=False)


class AdminReportSerializer(serializers.ModelSerializer):
    """Serializer for report moderation listings."""

    reporter_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "reporter_name",
            "resource",
            "comment",
            "target_type",
            "target_title",
            "reason_type",
            "message",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "resolution_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]

    def get_target_type(self, obj) -> str:
        return obj.get_target_type()

    def get_target_title(self, obj) -> str:
        return obj.get_target_title()

    def get_reporter_name(self, obj) -> str:
        return _user_display_name(obj.reporter)

    def get_reviewed_by_name(self, obj) -> str:
        if not obj.reviewed_by:
            return ""
        return _user_display_name(obj.reviewed_by)


class AdminReportUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating report status."""

    class Meta:
        model = Report
        fields = ["status", "resolution_note"]

    def validate_status(self, value):
        current = self.instance.status if self.instance else "open"
        if current in ["resolved", "dismissed"] and value != current:
            raise serializers.ValidationError(f"Cannot change status from {current}.")
        return value


class AdminReportResolveDismissSerializer(serializers.Serializer):
    """Payload for resolve/dismiss actions."""

    resolution_note = serializers.CharField(required=False, allow_blank=True)


class AdminAnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for announcement admin management."""

    created_by_name = serializers.SerializerMethodField()
    target_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "slug",
            "content",
            "announcement_type",
            "status",
            "target_faculty",
            "target_department",
            "target_course",
            "target_year_of_study",
            "target_summary",
            "is_pinned",
            "published_at",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj) -> str:
        if not obj.created_by:
            return ""
        return _user_display_name(obj.created_by)


class AdminStudyGroupSerializer(serializers.ModelSerializer):
    """Serializer for admin study group management."""

    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source="creator.email", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "description",
            "course",
            "course_name",
            "faculty",
            "faculty_name",
            "department",
            "department_name",
            "year_of_study",
            "privacy",
            "is_public",
            "allow_member_invites",
            "max_members",
            "member_count",
            "status",
            "created_by_name",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "course_name",
            "faculty_name",
            "department_name",
            "member_count",
            "created_by_name",
            "created_by_email",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj) -> str:
        return _user_display_name(obj.creator)

    def get_member_count(self, obj) -> int:
        annotated_count = getattr(obj, "active_member_count", None)
        if annotated_count is not None:
            return int(annotated_count)
        return obj.memberships.filter(status="active").count()


class AdminStudyGroupUpdateSerializer(serializers.ModelSerializer):
    """Payload for admin study group updates."""

    class Meta:
        model = StudyGroup
        fields = [
            "name",
            "description",
            "is_public",
            "allow_member_invites",
            "max_members",
            "status",
        ]


class AdminFacultySerializer(serializers.ModelSerializer):
    """Serializer for faculty management."""

    department_count = serializers.SerializerMethodField()

    class Meta:
        model = Faculty
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "department_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_department_count(self, obj) -> int:
        return obj.departments.count()


class AdminDepartmentSerializer(serializers.ModelSerializer):
    """Serializer for department management."""

    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "faculty",
            "faculty_name",
            "name",
            "code",
            "description",
            "is_active",
            "course_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_course_count(self, obj) -> int:
        return obj.courses.count()


class AdminCourseSerializer(serializers.ModelSerializer):
    """Serializer for course management."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    unit_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "department",
            "department_name",
            "name",
            "code",
            "description",
            "duration_years",
            "is_active",
            "unit_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_unit_count(self, obj) -> int:
        return obj.units.count()


class AdminUnitSerializer(serializers.ModelSerializer):
    """Serializer for unit management."""

    course_name = serializers.CharField(source="course.name", read_only=True)

    class Meta:
        model = Unit
        fields = [
            "id",
            "course",
            "course_name",
            "name",
            "code",
            "description",
            "semester",
            "year_of_study",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AdminDashboardSerializer(serializers.Serializer):
    """Serializer for dashboard payload."""

    users = serializers.DictField()
    resources = serializers.DictField()
    reports = serializers.DictField()
    engagement = serializers.DictField()
    moderation = serializers.DictField()
    recent_resources = serializers.ListField()
    recent_reports = serializers.ListField()
