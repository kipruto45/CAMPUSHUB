"""
Core models for CampusHub.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides self-updating
    created and updated fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SlugifiedModel(models.Model):
    """
    Abstract base class that provides slug field.
    """

    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure unique slug
            original_slug = self.slug
            counter = 1
            while (
                self.__class__.objects.filter(slug=self.slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class SoftDeleteManager(models.Manager):
    """
    Manager that filters out soft-deleted objects.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_deleted(self):
        return super().get_queryset()

    def deleted_only(self):
        return super().get_queryset().filter(is_deleted=True)


class SoftDeleteModel(models.Model):
    """
    Abstract base class that provides soft delete functionality.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete the object."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self):
        """Permanently delete the object."""
        super().delete()

    def restore(self):
        """Restore a soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class AuditLog(models.Model):
    """
    Model for storing audit logs of all actions.
    """

    ACTION_CHOICES = [
        ("user_login", "User Login"),
        ("user_logout", "User Logout"),
        ("user_created", "User Created"),
        ("user_updated", "User Updated"),
        ("user_deleted", "User Deleted"),
        ("user_activated", "User Activated"),
        ("user_deactivated", "User Deactivated"),
        ("password_changed", "Password Changed"),
        ("password_reset", "Password Reset"),
        ("resource_created", "Resource Created"),
        ("resource_updated", "Resource Updated"),
        ("resource_deleted", "Resource Deleted"),
        ("resource_approved", "Resource Approved"),
        ("resource_rejected", "Resource Rejected"),
        ("resource_downloaded", "Resource Downloaded"),
        ("resource_viewed", "Resource Viewed"),
        ("faculty_created", "Faculty Created"),
        ("faculty_updated", "Faculty Updated"),
        ("faculty_deleted", "Faculty Deleted"),
        ("department_created", "Department Created"),
        ("department_updated", "Department Updated"),
        ("department_deleted", "Department Deleted"),
        ("course_created", "Course Created"),
        ("course_updated", "Course Updated"),
        ("course_deleted", "Course Deleted"),
        ("unit_created", "Unit Created"),
        ("unit_updated", "Unit Updated"),
        ("unit_deleted", "Unit Deleted"),
        ("report_created", "Report Created"),
        ("report_resolved", "Report Resolved"),
        ("report_dismissed", "Report Dismissed"),
        ("announcement_created", "Announcement Created"),
        ("announcement_updated", "Announcement Updated"),
        ("announcement_deleted", "Announcement Deleted"),
        ("announcement_published", "Announcement Published"),
        ("settings_updated", "Settings Updated"),
        ("backup_created", "Backup Created"),
        ("cache_cleared", "Cache Cleared"),
    ]

    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    description = models.TextField(blank=True)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"


class EmailCampaign(TimeStampedModel):
    """
    Model for email campaigns/ newsletters.
    """

    CAMPAIGN_TYPE_CHOICES = [
        ("general", "General"),
        ("announcement", "Announcement"),
        ("welcome", "Welcome Email"),
        ("notification", "Notification"),
        ("promotional", "Promotional"),
        ("digest", "Digest"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    campaign_type = models.CharField(
        max_length=20, choices=CAMPAIGN_TYPE_CHOICES, default="general"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft"
    )
    
    # Target filters
    target_filters = models.JSONField(default=dict, blank=True)
    
    # Statistics
    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_campaigns",
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["campaign_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


class APIUsageLog(TimeStampedModel):
    """
    Model for tracking API usage.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_usage_logs",
    )
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField()
    response_time_ms = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_size_bytes = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["endpoint", "-created_at"]),
            models.Index(fields=["method", "-created_at"]),
            models.Index(fields=["status_code", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"
