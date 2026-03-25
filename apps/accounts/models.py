"""
User models for CampusHub.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.encryption import (EncryptedFieldMixin, encrypted_charfield,
                                  encrypted_datefield, encrypted_textfield)


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email=None, password=None, **extra_fields):
        if not email:
            username = (extra_fields.get("username") or "").strip()
            if username:
                email = username
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        role = str(extra_fields.get("role", "STUDENT")).upper()
        if role not in {choice for choice, _ in User.ROLE_CHOICES}:
            role = "STUDENT"

        extra_fields["role"] = role
        extra_fields.setdefault("auth_provider", "email")
        extra_fields.setdefault("username", None)

        full_name = (extra_fields.get("full_name") or "").strip()
        if (
            full_name
            and not extra_fields.get("first_name")
            and not extra_fields.get("last_name")
        ):
            parts = full_name.split(" ", 1)
            extra_fields["first_name"] = parts[0]
            extra_fields["last_name"] = parts[1] if len(parts) > 1 else ""

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "ADMIN")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(EncryptedFieldMixin, AbstractUser):
    """Custom user model for CampusHub."""

    ROLE_CHOICES = [
        ("STUDENT", "Student"),
        ("INSTRUCTOR", "Instructor"),
        ("DEPARTMENT_HEAD", "Department Head"),
        ("SUPPORT_STAFF", "Support Staff"),
        ("MODERATOR", "Moderator"),
        ("ADMIN", "Admin"),
    ]

    AUTH_PROVIDER_CHOICES = [
        ("email", "Email"),
        ("google", "Google"),
        ("microsoft", "Microsoft"),
    ]

    SEMESTER_CHOICES = [
        (1, "Semester 1"),
        (2, "Semester 2"),
    ]

    email = models.EmailField(_("email address"), unique=True)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)

    full_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    phone_number = encrypted_charfield(max_length=20, blank=True)

    # Legacy aliases kept for backward compatibility with older modules.
    phone = encrypted_charfield(max_length=20, blank=True)
    student_id = encrypted_charfield(max_length=100, blank=True)

    profile_image = models.ImageField(
        upload_to="profiles/",
        default="defaults/profile.png",
        blank=True,
    )
    bio = encrypted_textfield(blank=True)
    date_of_birth = encrypted_datefield(null=True, blank=True)

    faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    year_of_study = models.PositiveIntegerField(null=True, blank=True)
    semester = models.PositiveSmallIntegerField(
        choices=SEMESTER_CHOICES, null=True, blank=True
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="STUDENT")
    auth_provider = models.CharField(
        max_length=20, choices=AUTH_PROVIDER_CHOICES, default="email"
    )

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_scheduled_at = models.DateTimeField(null=True, blank=True)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = encrypted_textfield(blank=True)

    last_activity = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["username"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_active", "is_verified"]),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.role:
            normalized = str(self.role).upper()
            allowed = {choice for choice, _ in self.ROLE_CHOICES}
            self.role = normalized if normalized in allowed else "STUDENT"
        else:
            self.role = "STUDENT"

        if self.auth_provider:
            normalized_provider = str(self.auth_provider).lower()
            allowed_providers = {choice for choice, _ in self.AUTH_PROVIDER_CHOICES}
            self.auth_provider = (
                normalized_provider
                if normalized_provider in allowed_providers
                else "email"
            )
        else:
            self.auth_provider = "email"

        if self.full_name:
            self.full_name = self.full_name.strip()

        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()

        if self.full_name and not (self.first_name or self.last_name):
            parts = self.full_name.split(" ", 1)
            self.first_name = parts[0]
            self.last_name = parts[1] if len(parts) > 1 else ""

        if self.phone_number and not self.phone:
            self.phone = self.phone_number
        elif self.phone and not self.phone_number:
            self.phone_number = self.phone

        if self.registration_number and not self.student_id:
            self.student_id = self.registration_number
        elif self.student_id and not self.registration_number:
            self.registration_number = self.student_id

        super().save(*args, **kwargs)

    def get_full_name(self):
        """Return the user's full name."""
        if self.full_name:
            return self.full_name
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        """Return the user's short display name."""
        if self.first_name:
            return self.first_name
        if self.full_name:
            return self.full_name.split(" ", 1)[0]
        return self.email.split("@")[0]

    @property
    def assigned_role_codes(self):
        """Return all known role codes for the user."""
        role_codes = set()
        if self.role:
            role_codes.add(str(self.role).upper())

        role_assignments_manager = getattr(self, "role_assignments", None)
        if role_assignments_manager is not None:
            role_codes.update(
                role_assignments_manager.filter(revoked_at__isnull=True).values_list(
                    "role_definition__code", flat=True
                )
            )

        if self.is_superuser:
            role_codes.add("ADMIN")
        return sorted(role_codes)

    def has_assigned_role(self, role_code: str) -> bool:
        """Check whether the user has a direct or assigned role."""
        normalized_role = str(role_code or "").strip().upper()
        if not normalized_role:
            return False
        return normalized_role in set(self.assigned_role_codes)

    @property
    def is_admin(self):
        return self.is_superuser or self.has_assigned_role("ADMIN")

    @property
    def is_moderator(self):
        return self.is_admin or self.has_assigned_role("MODERATOR")

    @property
    def is_student(self):
        return self.has_assigned_role("STUDENT")

    @property
    def is_instructor(self):
        return self.has_assigned_role("INSTRUCTOR")

    @property
    def is_department_head(self):
        return self.has_assigned_role("DEPARTMENT_HEAD")

    @property
    def is_support_staff(self):
        return self.has_assigned_role("SUPPORT_STAFF")

    def update_last_login(self):
        """Track login usage and last login timestamp."""
        now = timezone.now()
        self.login_count = (self.login_count or 0) + 1
        self.last_login = now
        self.last_activity = now
        self.save(
            update_fields=["login_count", "last_login", "last_activity", "updated_at"]
        )

    def increment_login_count(self):
        """Backward-compatible alias for login updates."""
        self.update_last_login()

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = timezone.now()
        self.save(update_fields=["last_activity", "updated_at"])

    @property
    def get_profile_image_url(self):
        """Return the profile image URL."""
        if self.profile_image:
            return self.profile_image.url
        return None

    def has_course_assigned(self):
        """Check if user has a course assigned."""
        return self.course is not None


class UserDevice(models.Model):
    """Store user device information for push notifications."""

    DEVICE_TYPE_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    device_name = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_used"]

    def __str__(self):
        return f"{self.user.email} - {self.device_type}"


class UserActivity(models.Model):
    """Track user activity."""

    ACTION_TYPES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("view", "View Resource"),
        ("download", "Download Resource"),
        ("upload", "Upload Resource"),
        ("bookmark", "Bookmark"),
        ("favorite", "Favorite"),
        ("rate", "Rate"),
        ("comment", "Comment"),
        ("search", "Search"),
        ("profile_update", "Profile Update"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_activities",
    )
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["resource", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.action}"


class UserConnection(models.Model):
    """Track social connections between users."""

    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="connections_from"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="connections_to"
    )
    connection_type = models.CharField(max_length=20)  # 'follow', 'friend'
    is_mutual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["from_user", "to_user", "connection_type"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user.email} {self.connection_type} {self.to_user.email}"


class UserSession(models.Model):
    """Track active user sessions."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity"]

    def __str__(self):
        return f"{self.user.email} - {self.ip_address}"

    def is_valid(self):
        """Check if session is still valid."""
        return self.is_active and timezone.now() < self.expires_at


class ProfileView(models.Model):
    """Track profile views."""

    profile_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profile_views_received"
    )
    viewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profile_views_made"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.viewer.email} viewed {self.profile_owner.email}'s profile"


class Profile(EncryptedFieldMixin, models.Model):
    """Extended user profile model."""

    STATUS_CHOICES = [
        ("incomplete", "Incomplete"),
        ("partial", "Partial"),
        ("complete", "Complete"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = encrypted_textfield(blank=True, max_length=500)
    date_of_birth = encrypted_datefield(null=True, blank=True)
    address = encrypted_charfield(max_length=255, blank=True)
    city = encrypted_charfield(max_length=100, blank=True)
    country = encrypted_charfield(max_length=100, blank=True)
    website = models.URLField(blank=True)
    facebook = encrypted_charfield(max_length=255, blank=True)
    twitter = encrypted_charfield(max_length=100, blank=True)
    linkedin = encrypted_charfield(max_length=100, blank=True)

    total_uploads = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    total_bookmarks = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)
    total_ratings = models.PositiveIntegerField(default=0)

    completion_percentage = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="incomplete"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        return f"Profile of {self.user.email}"

    def calculate_completion_percentage(self):
        """Calculate profile completion percentage."""
        fields = [
            self.user.full_name,
            self.user.registration_number,
            self.user.phone_number,
            self.user.faculty_id,
            self.user.department_id,
            self.user.course_id,
            self.user.year_of_study,
            self.bio,
            self.city,
            self.country,
            bool(self.user.profile_image),
        ]
        filled = sum(1 for field in fields if field)
        return int((filled / len(fields)) * 100)


class UserPreference(models.Model):
    """User preferences model."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    email_notifications = models.BooleanField(default=True)
    app_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=True)

    public_profile = models.BooleanField(default=True)
    show_email = models.BooleanField(default=False)
    show_activity = models.BooleanField(default=True)

    language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=50, default="Africa/Nairobi")
    theme = models.CharField(max_length=20, default="light")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"

class LinkedAccount(models.Model):
    """Linked OAuth providers for a user."""

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("microsoft", "Microsoft"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="linked_accounts"
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255)
    provider_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("provider", "provider_user_id")]
        indexes = [
            models.Index(fields=["user", "provider", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.provider}"


class UserPasskey(EncryptedFieldMixin, models.Model):
    """
    Stores WebAuthn/FIDO2 passkey credentials for users.
    Supports multiple passkeys per user and backup options.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="passkeys"
    )
    name = models.CharField(max_length=100, help_text="User-defined name for this passkey")
    credential_id = models.CharField(
        max_length=255, unique=True, help_text="Base64-encoded credential ID"
    )
    public_key = encrypted_textfield(help_text="Base64-encoded public key")
    sign_count = models.PositiveIntegerField(
        default=0, help_text="Signature counter for credential"
    )
    backup_eligible = models.BooleanField(
        default=False, help_text="Whether credential is backup-eligible"
    )
    backup_state = models.BooleanField(
        default=False, help_text="Current backup state of credential"
    )
    aaguid = encrypted_charfield(
        max_length=36, blank=True, help_text="Authenticator AAGUID"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"
        verbose_name = "User Passkey"
        verbose_name_plural = "User Passkeys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.name}"


class MagicLinkTokenHistory(models.Model):
    """
    Tracks used magic link tokens to ensure one-time use.
    """

    token_hash = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="magic_link_tokens"
    )
    used_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        app_label = "accounts"
        verbose_name = "Magic Link Token History"
        verbose_name_plural = "Magic Link Token Histories"
        ordering = ["-used_at"]

    def __str__(self):
        return f"Magic link used by {self.user.email} at {self.used_at}"
