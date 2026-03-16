"""
Models for ratings app.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Rating(TimeStampedModel):
    """Model for resource ratings."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings"
    )
    resource = models.ForeignKey(
        "resources.Resource", on_delete=models.CASCADE, related_name="ratings"
    )
    value = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        verbose_name = "Rating"
        verbose_name_plural = "Ratings"
        unique_together = ["user", "resource"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.resource.title}: {self.value}"
