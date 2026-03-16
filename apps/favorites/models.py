"""
Models for favorites app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class FavoriteType:
    """Favorite type constants."""

    RESOURCE = "resource"
    PERSONAL_FILE = "personal_file"
    FOLDER = "folder"

    CHOICES = [
        (RESOURCE, "Resource"),
        (PERSONAL_FILE, "Personal File"),
        (FOLDER, "Folder"),
    ]


class Favorite(TimeStampedModel):
    """Model for favorited items."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    favorite_type = models.CharField(max_length=20, choices=FavoriteType.CHOICES)
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="favorites",
    )
    personal_file = models.ForeignKey(
        "resources.PersonalResource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="favorites",
    )
    personal_folder = models.ForeignKey(
        "resources.PersonalFolder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="favorites",
    )

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"
        ordering = ["-created_at"]
        unique_together = [
            ["user", "resource"],
            ["user", "personal_file"],
            ["user", "personal_folder"],
        ]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "favorite_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_favorite_type_display()}"

    @property
    def target_title(self):
        """Get the title/name of the favorited item."""
        if self.resource:
            return self.resource.title
        elif self.personal_file:
            return self.personal_file.name
        elif self.personal_folder:
            return self.personal_folder.name
        return "Unknown"

    @property
    def target(self):
        """Get the actual target object."""
        if self.resource:
            return self.resource
        elif self.personal_file:
            return self.personal_file
        elif self.personal_folder:
            return self.personal_folder
        return None
