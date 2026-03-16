"""
Models for comments app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Comment(TimeStampedModel):
    """Model for resource comments."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    resource = models.ForeignKey(
        "resources.Resource", on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = models.TextField()
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    moderation_hidden = models.BooleanField(default=False)
    moderation_hidden_content = models.TextField(blank=True)

    class Meta:
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.user.email} on {self.resource.title}"
