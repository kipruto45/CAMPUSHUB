"""
Models for activity tracking app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ActivityType:
    """Activity type constants."""

    VIEWED_RESOURCE = "viewed_resource"
    OPENED_PERSONAL_FILE = "opened_personal_file"
    DOWNLOADED_RESOURCE = "downloaded_resource"
    DOWNLOADED_PERSONAL_FILE = "downloaded_personal_file"
    BOOKMARKED_RESOURCE = "bookmarked_resource"
    CREATED_RESOURCE = "created_resource"
    UPDATED_RESOURCE = "updated_resource"
    COMMENTED = "commented"
    RATED = "rated"
    SHARED_RESOURCE = "shared_resource"

    CHOICES = [
        (VIEWED_RESOURCE, "Viewed Resource"),
        (OPENED_PERSONAL_FILE, "Opened Personal File"),
        (DOWNLOADED_RESOURCE, "Downloaded Resource"),
        (DOWNLOADED_PERSONAL_FILE, "Downloaded Personal File"),
        (BOOKMARKED_RESOURCE, "Bookmarked Resource"),
        (CREATED_RESOURCE, "Created Resource"),
        (UPDATED_RESOURCE, "Updated Resource"),
        (COMMENTED, "Commented"),
        (RATED, "Rated"),
        (SHARED_RESOURCE, "Shared Resource"),
    ]


class RecentActivity(TimeStampedModel):
    """Model for tracking recent user activity."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recent_activities",
    )
    activity_type = models.CharField(max_length=50, choices=ActivityType.CHOICES)
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    personal_file = models.ForeignKey(
        "resources.PersonalResource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    bookmark = models.ForeignKey(
        "bookmarks.Bookmark",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Recent Activity"
        verbose_name_plural = "Recent Activities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "activity_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_activity_type_display()}"

    @property
    def target_title(self):
        """Get the title/name of the activity target."""
        if self.resource:
            return self.resource.title
        elif self.personal_file:
            return self.personal_file.title
        elif self.bookmark and self.bookmark.resource:
            return self.bookmark.resource.title
        return "Unknown"

    @property
    def target_type(self):
        """Get the type of activity target."""
        if self.resource:
            return "resource"
        elif self.personal_file:
            return "personal_file"
        elif self.bookmark:
            return "bookmark"
        return "unknown"
