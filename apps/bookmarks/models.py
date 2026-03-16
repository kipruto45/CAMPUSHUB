"""
Models for bookmarks app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Bookmark(TimeStampedModel):
    """Model for bookmarked resources."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    resource = models.ForeignKey(
        "resources.Resource", on_delete=models.CASCADE, related_name="bookmarks"
    )

    class Meta:
        verbose_name = "Bookmark"
        verbose_name_plural = "Bookmarks"
        unique_together = ["user", "resource"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.resource.title}"
