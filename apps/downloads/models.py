"""
Models for downloads app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Download(TimeStampedModel):
    """Model for tracking resource downloads."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="downloads",
    )
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="downloads",
        null=True,
        blank=True,
    )
    personal_file = models.ForeignKey(
        "resources.PersonalResource",
        on_delete=models.CASCADE,
        related_name="downloads",
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "Download"
        verbose_name_plural = "Downloads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        if self.resource:
            return f"{self.user.email} - {self.resource.title}"
        elif self.personal_file:
            return f"{self.user.email} - {self.personal_file.title}"
        return f"{self.user.email} - Download {self.id}"

    @property
    def download_title(self):
        """Get the title/name of the downloaded item."""
        if self.resource:
            return self.resource.title
        elif self.personal_file:
            return self.personal_file.title
        return "Unknown"

    @property
    def download_type(self):
        """Get the type of download."""
        if self.resource:
            return "resource"
        elif self.personal_file:
            return "personal_file"
        return "unknown"
