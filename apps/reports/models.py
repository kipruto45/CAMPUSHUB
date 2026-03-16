"""
Models for reports app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Report(TimeStampedModel):
    """Model for reporting inappropriate content."""

    REASON_CHOICES = [
        ("inappropriate", "Inappropriate Content"),
        ("duplicate", "Duplicate Content"),
        ("wrong_category", "Wrong Category"),
        ("broken_file", "Broken File"),
        ("copyright", "Copyright Violation"),
        ("spam", "Spam"),
        ("abusive", "Abusive Behavior"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_review", "In Review"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made"
    )

    # Can report either a resource or a comment
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )

    comment = models.ForeignKey(
        "comments.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )

    reason_type = models.CharField(max_length=30, choices=REASON_CHOICES)
    message = models.TextField(help_text="Detailed explanation of the issue")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_reviewed",
    )

    resolution_note = models.TextField(
        blank=True, help_text="Notes about the resolution"
    )

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["reason_type"]),
        ]

    def __str__(self):
        target = self.resource.title if self.resource else f"Comment {self.comment_id}"
        return f"Report #{self.id} - {target} - {self.reason_type}"

    def get_target_type(self):
        """Get the type of content being reported."""
        if self.resource:
            return "resource"
        elif self.comment:
            return "comment"
        return "unknown"

    def get_target_title(self):
        """Get human-readable title of the reported target."""
        if self.resource:
            return self.resource.title
        if self.comment:
            return f"Comment by {self.comment.user.full_name}"
        return "Unknown content"
