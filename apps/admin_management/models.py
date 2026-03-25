"""
Content Calendar - Schedule and manage content publishing.
"""

import secrets

from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4


class ContentCalendarEvent(models.Model):
    """
    Events for content calendar - schedule announcements, posts, and content.
    """
    
    class EventType(models.TextChoices):
        ANNOUNCEMENT = 'announcement', 'Announcement'
        POST = 'post', 'Social Post'
        EMAIL = 'email', 'Email Campaign'
        NOTIFICATION = 'notification', 'Push Notification'
        PROMOTION = 'promotion', 'Promotion'
        MAINTENANCE = 'maintenance', 'Maintenance'
        EVENT = 'event', 'Event'
    
    class EventStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.DRAFT)
    
    # Scheduling
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_all_day = models.BooleanField(default=False)
    
    # Content reference
    related_object_type = models.CharField(max_length=50, blank=True)  # announcement, resource, etc.
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Target audience
    target_faculty_id = models.UUIDField(null=True, blank=True)
    target_department_id = models.UUIDField(null=True, blank=True)
    target_year_level = models.IntegerField(null=True, blank=True)
    is_global = models.BooleanField(default=True)
    
    # Recurrence
    recurrence_rule = models.CharField(max_length=255, blank=True)  # RRULE format
    
    # Visual
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    icon = models.CharField(max_length=50, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='calendar_events_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_events_published'
    )
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_content_calendar'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['start_datetime']),
            models.Index(fields=['event_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.event_type})"
    
    def publish(self, user):
        """Publish the event."""
        self.status = self.EventStatus.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save()
    
    def cancel(self):
        """Cancel the event."""
        self.status = self.EventStatus.CANCELLED
        self.save()
    
    @property
    def is_upcoming(self):
        """Check if event is upcoming."""
        return self.start_datetime > timezone.now() and self.status in [self.EventStatus.DRAFT, self.EventStatus.SCHEDULED]
    
    @property
    def is_past(self):
        """Check if event is in the past."""
        return self.end_datetime and self.end_datetime < timezone.now()


class CalendarCategory(models.Model):
    """Custom categories for calendar events."""
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    icon = models.CharField(max_length=50, blank=True)
    event_types = models.JSONField(default=list)  # List of event types
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_calendar_categories'
        verbose_name_plural = 'Calendar Categories'
    
    def __str__(self):
        return self.name


class CalendarTemplate(models.Model):
    """Templates for recurring calendar events."""
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=ContentCalendarEvent.EventType.choices)
    
    # Default values
    default_duration_hours = models.IntegerField(default=1)
    default_color = models.CharField(max_length=7, default='#3B82F6')
    default_target = models.JSONField(default=dict)
    
    # Template content
    title_template = models.CharField(max_length=255)
    description_template = models.TextField(blank=True)
    
    recurrence_pattern = models.CharField(max_length=255)  # e.g., "WEEKLY:MONDAY"
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_calendar_templates'
    
    def __str__(self):
        return self.name
    
    def create_events(self, start_date, end_date, user):
        """Generate events from template."""
        from datetime import timedelta
        
        events = []
        current_date = start_date
        
        while current_date <= end_date:
            event = ContentCalendarEvent(
                title=self.title_template,
                description=self.description_template,
                event_type=self.event_type,
                start_datetime=current_date,
                end_datetime=current_date + timedelta(hours=self.default_duration_hours),
                color=self.default_color,
                created_by=user,
                related_object_type='template',
                related_object_id=self.id
            )
            events.append(event)
            
            # Move to next occurrence based on recurrence
            if 'WEEKLY' in self.recurrence_pattern:
                current_date += timedelta(weeks=1)
            elif 'DAILY' in self.recurrence_pattern:
                current_date += timedelta(days=1)
            elif 'MONTHLY' in self.recurrence_pattern:
                current_date += timedelta(days=30)
            else:
                break
        
        return ContentCalendarEvent.objects.bulk_create(events)


class AdminInvitationRole(models.Model):
    """Admin-managed role catalog for invitations and permission presets."""

    ROLE_CHOICES = [
        ("STUDENT", "Student"),
        ("INSTRUCTOR", "Instructor"),
        ("DEPARTMENT_HEAD", "Department Head"),
        ("SUPPORT_STAFF", "Support Staff"),
        ("MODERATOR", "Moderator"),
        ("ADMIN", "Admin"),
    ]

    code = models.CharField(max_length=20, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_assignable = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    requires_superuser = models.BooleanField(default=False)
    inviter_permissions = models.JSONField(default=list, blank=True)
    permission_preset = models.JSONField(default=list, blank=True)
    email_subject_template = models.CharField(max_length=255, blank=True)
    email_body_template = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "admin_management"
        db_table = "admin_invitation_roles"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "is_assignable"]),
        ]
        permissions = (
            ("can_invite_admin_role", "Can invite users with the Admin role"),
            (
                "can_invite_department_head_role",
                "Can invite users with the Department Head role",
            ),
        )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        normalized_code = str(self.code or "").strip().upper()
        valid_codes = {choice for choice, _ in self.ROLE_CHOICES}
        self.code = normalized_code if normalized_code in valid_codes else "STUDENT"
        if not self.name:
            self.name = self.get_code_display()
        self.metadata = self.metadata or {}
        self.inviter_permissions = list(self.inviter_permissions or [])
        self.permission_preset = list(self.permission_preset or [])
        super().save(*args, **kwargs)


class AdminInvitationBatch(models.Model):
    """Track bulk invitation imports and outcomes."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)
    source_file_name = models.CharField(max_length=255, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_invitation_batches",
    )
    total_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "admin_management"
        db_table = "admin_invitation_batches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.name or f"Invitation batch {self.id}"

    @property
    def success_rate(self) -> float:
        if not self.total_rows:
            return 0.0
        return round((self.successful_rows / self.total_rows) * 100, 2)


class AdminRoleInvitation(models.Model):
    """Invite a user into one or more specific CampusHub roles."""

    class InvitationSource(models.TextChoices):
        API = "api", "API"
        ADMIN = "admin", "Admin"
        CSV = "csv", "CSV Upload"

    ROLE_CHOICES = AdminInvitationRole.ROLE_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    note = models.TextField(blank=True)
    source = models.CharField(
        max_length=20,
        choices=InvitationSource.choices,
        default=InvitationSource.API,
    )
    metadata = models.JSONField(default=dict, blank=True)
    accepted_metadata = models.JSONField(default=dict, blank=True)
    email_subject = models.CharField(max_length=255, blank=True)
    email_body = models.TextField(blank=True)
    token = models.CharField(max_length=255, unique=True, db_index=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_role_invitations_sent",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_role_invitations_accepted",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_role_invitations_revoked",
    )
    batch = models.ForeignKey(
        "admin_management.AdminInvitationBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "admin_management"
        db_table = "admin_role_invitations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "created_at"]),
            models.Index(fields=["role", "created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def __str__(self):
        return f"{self.email} -> {', '.join(self.get_role_codes())}"

    def save(self, *args, **kwargs):
        from apps.accounts.models import User

        self.email = (self.email or "").strip().lower()
        allowed_roles = {choice for choice, _ in User.ROLE_CHOICES}
        normalized_role = str(self.role or "").upper()
        self.role = normalized_role if normalized_role in allowed_roles else "STUDENT"
        self.metadata = self.metadata or {}
        self.accepted_metadata = self.accepted_metadata or {}
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def get_role_assignments(self):
        cached = getattr(self, "_prefetched_objects_cache", {})
        if "invitation_roles" in cached:
            return cached["invitation_roles"]
        return list(self.invitation_roles.select_related("role_definition").all())

    def get_role_codes(self):
        assignments = self.get_role_assignments()
        if assignments:
            assignment_codes = [
                assignment.role_definition.code
                for assignment in assignments
                if assignment.role_definition_id
            ]
            requested_roles = [
                str(role_code or "").strip().upper()
                for role_code in (self.metadata or {}).get("requested_roles", [])
                if str(role_code or "").strip()
            ]
            if requested_roles:
                ordered_codes = []
                for role_code in requested_roles:
                    if role_code in assignment_codes and role_code not in ordered_codes:
                        ordered_codes.append(role_code)
                for role_code in assignment_codes:
                    if role_code not in ordered_codes:
                        ordered_codes.append(role_code)
                return ordered_codes
            return assignment_codes
        return [self.role] if self.role else []

    def get_role_names(self):
        assignments = self.get_role_assignments()
        if assignments:
            return [
                assignment.role_definition.name
                for assignment in assignments
                if assignment.role_definition_id
            ]
        return [self.get_role_display()] if self.role else []

    @property
    def status(self) -> str:
        if self.accepted_at:
            return "accepted"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "pending"

    @property
    def is_active(self) -> bool:
        return self.status == "pending"

    @property
    def primary_role_name(self) -> str:
        assignments = self.get_role_assignments()
        primary_assignment = next(
            (assignment for assignment in assignments if assignment.is_primary),
            None,
        )
        if primary_assignment and primary_assignment.role_definition_id:
            return primary_assignment.role_definition.name
        return self.get_role_display()

    def is_valid(self) -> bool:
        return self.is_active


class AdminRoleInvitationRole(models.Model):
    """Associate invitations with one or more requested roles."""

    invitation = models.ForeignKey(
        "admin_management.AdminRoleInvitation",
        on_delete=models.CASCADE,
        related_name="invitation_roles",
    )
    role_definition = models.ForeignKey(
        "admin_management.AdminInvitationRole",
        on_delete=models.CASCADE,
        related_name="invitation_assignments",
    )
    is_primary = models.BooleanField(default=False)
    permission_preset = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "admin_management"
        db_table = "admin_role_invitation_roles"
        ordering = ["-is_primary", "role_definition__sort_order", "role_definition__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["invitation", "role_definition"],
                name="admin_role_invitation_unique_role",
            ),
        ]

    def __str__(self):
        return f"{self.invitation.email} -> {self.role_definition.code}"

    def save(self, *args, **kwargs):
        self.permission_preset = list(
            self.permission_preset or getattr(self.role_definition, "permission_preset", []) or []
        )
        self.metadata = self.metadata or {}
        super().save(*args, **kwargs)


class AdminUserRoleAssignment(models.Model):
    """Persist role associations and applied permission presets for users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role_definition = models.ForeignKey(
        "admin_management.AdminInvitationRole",
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )
    invitation = models.ForeignKey(
        "admin_management.AdminRoleInvitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_role_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_role_assignments",
    )
    is_primary = models.BooleanField(default=False)
    permission_preset = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "admin_management"
        db_table = "admin_user_role_assignments"
        ordering = ["-is_primary", "role_definition__sort_order", "role_definition__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role_definition"],
                name="admin_user_unique_role_assignment",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.role_definition.code}"

    def save(self, *args, **kwargs):
        self.permission_preset = list(
            self.permission_preset or getattr(self.role_definition, "permission_preset", []) or []
        )
        self.metadata = self.metadata or {}
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
