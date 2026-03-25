"""
Serializers for accounts app.
"""


from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from apps.courses.models import Course
from apps.courses.serializers import CourseSerializer
from apps.faculties.models import Department, Faculty
from apps.faculties.serializers import DepartmentSerializer, FacultySerializer

from .models import LinkedAccount, Profile, User, UserActivity, UserPreference
from .services import (LinkedAccountService, ProfileCompletionService,
                       ProfileStatsService, ProfileValidationService)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    profile_image_url = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "registration_number",
            "phone_number",
            "profile_image",
            "profile_image_url",
            "avatar",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
            "role",
            "auth_provider",
            "is_verified",
            "is_active",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "date_joined",
            "last_login",
            "auth_provider",
        ]

    def get_avatar(self, obj) -> str | None:
        if obj.profile_image:
            if hasattr(obj.profile_image, "url"):
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image
        return None

    def get_profile_image_url(self, obj) -> str | None:
        if obj.profile_image:
            if hasattr(obj.profile_image, "url"):
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for User model."""

    faculty_details = FacultySerializer(source="faculty", read_only=True)
    department_details = DepartmentSerializer(source="department", read_only=True)
    course_details = CourseSerializer(source="course", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "registration_number",
            "phone_number",
            "profile_image",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
            "role",
            "auth_provider",
            "is_verified",
            "is_active",
            "date_joined",
            "last_login",
            "faculty_details",
            "department_details",
            "course_details",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "date_joined",
            "last_login",
            "auth_provider",
        ]


class UserSummarySerializer(serializers.ModelSerializer):
    """Compact serializer used by dashboard and lightweight listings."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "profile_image",
            "role",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
        ]
        read_only_fields = fields


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    role = serializers.CharField(required=False, default="STUDENT")

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "full_name",
            "registration_number",
            "phone_number",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "role",
        ]

    def validate_role(self, value):
        normalized_role = str(value).strip().upper()
        allowed_roles = {choice for choice, _ in User.ROLE_CHOICES}
        if normalized_role not in allowed_roles:
            raise serializers.ValidationError("Invalid role.")
        if normalized_role != "STUDENT":
            raise serializers.ValidationError("Self-signup can only use STUDENT role.")
        return "STUDENT"

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
            registration_number=validated_data.get("registration_number"),
            phone_number=validated_data.get("phone_number", ""),
            faculty=validated_data.get("faculty"),
            department=validated_data.get("department"),
            course=validated_data.get("course"),
            year_of_study=validated_data.get("year_of_study"),
            role="STUDENT",
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField(required=False, allow_blank=True)
    registration_number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    two_factor_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    def validate(self, attrs):
        email = attrs.get("email", "").strip()
        registration_number = attrs.get("registration_number", "").strip()
        password = attrs.get("password")

        # Determine the login identifier
        login_identifier = email or registration_number
        
        if not login_identifier:
            raise serializers.ValidationError(
                'Must include "email" or "registration_number" and "password".'
            )
        
        if not password:
            raise serializers.ValidationError('Must include "password".')

        # Try to find user by email or registration number
        user = None
        if email:
            user = authenticate(
                request=self.context.get("request"), username=email, password=password
            )
        
        # If not found by email, try registration number
        if not user and registration_number:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user_obj = User.objects.get(registration_number__iexact=registration_number)
                if user_obj.check_password(password):
                    user = user_obj
            except User.DoesNotExist:
                pass

        if not user:
            raise AuthenticationFailed("Invalid email/registration number or password.")
        
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")

        # Enforce 2FA if enabled
        try:
            from apps.two_factor.services import TwoFactorService

            if TwoFactorService.is_2fa_required(user):
                code = (attrs.get("two_factor_code") or "").strip()
                if not code:
                    raise AuthenticationFailed(
                        "Two-factor code required.",
                        code="two_factor_required",
                    )
                if not TwoFactorService.verify_2fa_code(user, code):
                    raise AuthenticationFailed("Invalid two-factor code.")
        except AuthenticationFailed:
            raise
        except Exception:
            # Fail closed for safety if 2FA is enabled but verification fails
            raise AuthenticationFailed("Two-factor verification failed.")
        
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""

    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile model."""

    class Meta:
        model = Profile
        fields = [
            "id",
            "bio",
            "date_of_birth",
            "address",
            "city",
            "country",
            "website",
            "facebook",
            "twitter",
            "linkedin",
            "total_uploads",
            "total_downloads",
            "total_bookmarks",
            "total_comments",
            "total_ratings",
        ]
        read_only_fields = [
            "id",
            "total_uploads",
            "total_downloads",
            "total_bookmarks",
            "total_comments",
            "total_ratings",
        ]


class UserActivitySerializer(serializers.ModelSerializer):
    """Serializer for UserActivity model."""

    class Meta:
        model = UserActivity
        fields = [
            "id",
            "action",
            "description",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile with profile data."""

    profile = ProfileSerializer()
    profile_image_url = serializers.SerializerMethodField()
    # Add avatar field for mobile compatibility
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "registration_number",
            "phone_number",
            "profile_image",
            "profile_image_url",
            "avatar",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
            "role",
            "auth_provider",
            "is_verified",
            "is_active",
            "date_joined",
            "profile",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "auth_provider",
            "is_verified",
            "date_joined",
        ]

    def get_avatar(self, obj) -> str | None:
        """Return avatar URL for mobile app."""
        if obj.profile_image:
            if hasattr(obj.profile_image, 'url'):
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image
        return None

    def get_profile_image_url(self, obj) -> str | None:
        if obj.profile_image:
            # Handle both ImageField (file) and CharField (URL string)
            if hasattr(obj.profile_image, 'url'):
                # It's an ImageField file
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                # It's a URL string
                return obj.profile_image
        return None


# ============================================
# New Profile Management Serializers
# ============================================


class UserPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for UserPreference model."""

    class Meta:
        model = UserPreference
        fields = [
            "id",
            "email_notifications",
            "app_notifications",
            "push_notifications",
            "weekly_digest",
            "public_profile",
            "show_email",
            "show_activity",
            "theme",
            "language",
            "timezone",
        ]
        read_only_fields = ["id"]


class LinkedAccountSerializer(serializers.ModelSerializer):
    """Serializer for LinkedAccount model."""

    provider_display = serializers.CharField(
        source="get_provider_display", read_only=True
    )

    class Meta:
        model = LinkedAccount
        fields = [
            "id",
            "provider",
            "provider_display",
            "provider_email",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class ProfileDetailSerializer(serializers.ModelSerializer):
    """
    Enhanced profile serializer with completion, linked accounts, and stats.
    Used for the main profile endpoint.
    """

    profile = ProfileSerializer()
    preferences = UserPreferenceSerializer()
    profile_image_url = serializers.SerializerMethodField()
    completion = serializers.SerializerMethodField()
    linked_providers = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    academic_badge = serializers.SerializerMethodField()
    faculty_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    # Add avatar field for mobile compatibility
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            # Personal info
            "id",
            "email",
            "full_name",
            "registration_number",
            "phone_number",
            "profile_image",
            "profile_image_url",
            "avatar",
            # Academic info
            "faculty",
            "faculty_name",
            "department",
            "department_name",
            "course",
            "course_name",
            "year_of_study",
            "semester",
            "academic_badge",
            # Account info
            "role",
            "auth_provider",
            "is_verified",
            "is_active",
            "date_joined",
            "last_login",
            # Extended profile
            "profile",
            "preferences",
            # Additional data
            "completion",
            "linked_providers",
            "stats",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "auth_provider",
            "is_verified",
            "date_joined",
            "last_login",
        ]

    def get_avatar(self, obj) -> str | None:
        """Return avatar URL for mobile app."""
        if obj.profile_image:
            if hasattr(obj.profile_image, 'url'):
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image
        return None

    def get_profile_image_url(self, obj) -> str | None:
        if obj.profile_image:
            # Handle both ImageField (file) and CharField (URL string)
            if hasattr(obj.profile_image, 'url'):
                # It's an ImageField file
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(obj.profile_image.url)
            else:
                # It's a URL string
                return obj.profile_image
        return None

    def get_completion(self, obj) -> dict:
        """Get profile completion details."""
        return ProfileCompletionService.calculate_completion(obj)

    def get_linked_providers(self, obj) -> list[str]:
        """Get list of linked providers."""
        return LinkedAccountService.get_linked_providers(obj)

    def get_stats(self, obj) -> dict:
        """Get user statistics."""
        return ProfileStatsService.get_user_stats(obj)

    def get_academic_badge(self, obj) -> str | None:
        """Generate academic badge text."""
        if obj.year_of_study and obj.course:
            return f"Year {obj.year_of_study} {obj.course.name}"
        elif obj.year_of_study:
            return f"Year {obj.year_of_study}"
        return None

    def get_faculty_name(self, obj) -> str:
        return obj.faculty.name if obj.faculty else ""

    def get_department_name(self, obj) -> str:
        return obj.department.name if obj.department else ""

    def get_course_name(self, obj) -> str:
        return obj.course.name if obj.course else ""


class ProfilePhotoUploadSerializer(serializers.Serializer):
    """Serializer for profile photo upload."""

    profile_image = serializers.ImageField(
        help_text="Profile image file (max 5MB, jpg/png/gif)"
    )

    def validate_profile_image(self, value):
        """Validate image file."""
        # File size validation (5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image file size must be less than 5MB.")

        # File type validation
        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/heic",
            "image/heif",
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Invalid image type. Allowed: jpg, png, gif."
            )

        return value


class ProfileUpdateSerializer(serializers.Serializer):
    """
    Combined serializer for profile updates.
    Handles both User and Profile updates.
    """

    # User fields
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    registration_number = serializers.CharField(required=False, allow_blank=True)
    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(), required=False, allow_null=True
    )
    year_of_study = serializers.IntegerField(required=False, allow_null=True)
    semester = serializers.IntegerField(required=False, allow_null=True)

    # Profile fields
    bio = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    facebook = serializers.CharField(required=False, allow_blank=True)
    twitter = serializers.CharField(required=False, allow_blank=True)
    linkedin = serializers.CharField(required=False, allow_blank=True)

    def validate_phone_number(self, value):
        if value:
            is_valid, error = ProfileValidationService.validate_phone_number(value)
            if not is_valid:
                raise serializers.ValidationError(error)
        return value

    def validate_year_of_study(self, value):
        if value is not None:
            is_valid, error = ProfileValidationService.validate_year_of_study(value)
            if not is_valid:
                raise serializers.ValidationError(error)
        return value

    def validate_semester(self, value):
        if value is not None:
            is_valid, error = ProfileValidationService.validate_semester(value)
            if not is_valid:
                raise serializers.ValidationError(error)
        return value

    def validate_registration_number(self, value):
        if value:
            user = (
                self.context.get("request").user
                if self.context.get("request")
                else None
            )
            is_valid, error = ProfileValidationService.validate_registration_number(
                value, user
            )
            if not is_valid:
                raise serializers.ValidationError(error)
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(), required=False, allow_null=True
    )
    # Accept string (URL or path) for profile_image - handled in view
    profile_image = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = User
        fields = [
            "full_name",
            "phone_number",
            "registration_number",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
            "profile_image",
        ]

    def validate_phone_number(self, value):
        """Validate phone number format."""
        if value:
            is_valid, error = ProfileValidationService.validate_phone_number(value)
            if not is_valid:
                raise serializers.ValidationError(error)
        return value

    def validate_year_of_study(self, value):
        """Validate year of study."""
        is_valid, error = ProfileValidationService.validate_year_of_study(value)
        if not is_valid:
            raise serializers.ValidationError(error)
        return value

    def validate_semester(self, value):
        """Validate semester."""
        is_valid, error = ProfileValidationService.validate_semester(value)
        if not is_valid:
            raise serializers.ValidationError(error)
        return value

    def validate_registration_number(self, value):
        """Validate registration number."""
        user = self.context.get("request").user if self.context.get("request") else None
        is_valid, error = ProfileValidationService.validate_registration_number(
            value, user
        )
        if not is_valid:
            raise serializers.ValidationError(error)
        return value


# ==================== Passwordless Authentication Serializers ====================


class PasskeyRegistrationRequestSerializer(serializers.Serializer):
    """Serializer for passkey registration request."""

    name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Optional name for the passkey"
    )


class PasskeyRegistrationCompleteSerializer(serializers.Serializer):
    """Serializer for completing passkey registration."""

    credential = serializers.DictField(
        help_text="The credential data from the WebAuthn authenticator"
    )
    name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Optional name for the passkey"
    )


class PasskeyAuthenticationStartSerializer(serializers.Serializer):
    """Serializer for starting passkey authentication."""

    user_id = serializers.IntegerField(
        required=False,
        help_text="Optional user ID to authenticate with their passkeys"
    )


class PasskeyAuthenticationCompleteSerializer(serializers.Serializer):
    """Serializer for completing passkey authentication."""

    credential = serializers.DictField(
        help_text="The credential data from the WebAuthn authenticator"
    )


class PasskeyInfoSerializer(serializers.Serializer):
    """Serializer for passkey information."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    credential_id = serializers.CharField()
    sign_count = serializers.IntegerField()
    backup_eligible = serializers.BooleanField()
    backup_state = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    last_used_at = serializers.DateTimeField(allow_null=True)


class PasskeyDeleteSerializer(serializers.Serializer):
    """Serializer for deleting a passkey."""

    passkey_id = serializers.IntegerField(
        help_text="ID of the passkey to delete"
    )


class PasskeyUpdateSerializer(serializers.Serializer):
    """Serializer for updating passkey details."""

    passkey_id = serializers.IntegerField(
        help_text="ID of the passkey to update"
    )
    name = serializers.CharField(
        max_length=100,
        help_text="New name for the passkey"
    )


class MagicLinkRequestSerializer(serializers.Serializer):
    """Serializer for magic link request."""

    email = serializers.EmailField(
        help_text="User's email address"
    )


class MagicLinkConsumeSerializer(serializers.Serializer):
    """Serializer for consuming a magic link."""

    token = serializers.CharField(
        help_text="The magic link token"
    )
