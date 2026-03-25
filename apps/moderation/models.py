"""
Models for moderation app.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class ModerationLog(TimeStampedModel):
    """Model for moderation logs."""

    ACTION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("flagged", "Flagged"),
        ("removed", "Removed"),
        ("locked", "Locked"),
        ("unlocked", "Unlocked"),
        ("hidden", "Hidden"),
        ("restored", "Restored"),
        ("archived", "Archived"),
    ]

    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="moderation_logs",
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        "comments.Comment",
        on_delete=models.CASCADE,
        related_name="moderation_logs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderation_logs",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderation_actions",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Moderation Log"
        verbose_name_plural = "Moderation Logs"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(resource__isnull=False) | Q(comment__isnull=False) | Q(user__isnull=False),
                name="moderation_log_has_target",
            )
        ]

    def __str__(self):
        if self.resource:
            target = self.resource.title
        elif self.comment:
            target = f"Comment {self.comment_id}"
        elif self.user:
            target = f"User {self.user.email}"
        else:
            target = "Unknown target"
        return f"{target} - {self.action}"


class AdminActivityLog(TimeStampedModel):
    """Model for tracking admin activities across the platform."""

    ACTION_CHOICES = [
        # Resource actions
        ("resource_approved", "Resource Approved"),
        ("resource_rejected", "Resource Rejected"),
        ("resource_flagged", "Resource Flagged"),
        ("resource_archived", "Resource Archived"),
        ("resource_deleted", "Resource Deleted"),
        ("resource_restored", "Resource Restored"),
        # Report actions
        ("report_resolved", "Report Resolved"),
        ("report_dismissed", "Report Dismissed"),
        # User actions
        ("user_suspended", "User Suspended"),
        ("user_activated", "User Activated"),
        ("user_role_updated", "User Role Updated"),
        ("user_invitation_created", "User Invitation Created"),
        ("user_invitation_sent", "User Invitation Sent"),
        ("user_invitation_batch_created", "User Invitation Batch Created"),
        ("user_invitation_revoked", "User Invitation Revoked"),
        ("user_invitation_accepted", "User Invitation Accepted"),
        # Announcement actions
        ("announcement_published", "Announcement Published"),
        ("announcement_archived", "Announcement Archived"),
        # Academic actions
        ("faculty_created", "Faculty Created"),
        ("faculty_updated", "Faculty Updated"),
        ("department_created", "Department Created"),
        ("department_updated", "Department Updated"),
        ("course_created", "Course Created"),
        ("course_updated", "Course Updated"),
        ("unit_created", "Unit Created"),
        ("unit_updated", "Unit Updated"),
    ]

    TARGET_TYPE_CHOICES = [
        ("resource", "Resource"),
        ("report", "Report"),
        ("user", "User"),
        ("announcement", "Announcement"),
        ("faculty", "Faculty"),
        ("department", "Department"),
        ("course", "Course"),
        ("unit", "Unit"),
        ("system", "System"),
        ("role_invitation", "Role Invitation"),
        ("role_invitation_batch", "Role Invitation Batch"),
    ]

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_activity_logs",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=30, choices=TARGET_TYPE_CHOICES)
    target_id = models.CharField(max_length=50)
    target_title = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "Admin Activity Log"
        verbose_name_plural = "Admin Activity Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["admin", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.admin.email} - {self.action} - {self.target_type}:{self.target_id}"
