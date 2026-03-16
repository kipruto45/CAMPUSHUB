"""Models for recommendation profiles and cache."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UserInterestProfile(TimeStampedModel):
    """Denormalized user interest profile used for recommendation scoring."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_profile",
    )
    favorite_tags = models.JSONField(default=list, blank=True)
    favorite_units = models.JSONField(default=list, blank=True)
    favorite_resource_types = models.JSONField(default=list, blank=True)
    behavior_summary = models.JSONField(default=dict, blank=True)
    embedding_vector_key = models.CharField(max_length=255, blank=True)
    last_computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "User Interest Profile"
        verbose_name_plural = "User Interest Profiles"

    def __str__(self):
        return f"Interest profile for {self.user.email}"


class RecommendationCache(TimeStampedModel):
    """Cached recommendation rows for dashboard and for-you feeds."""

    CATEGORY_FOR_YOU = "for_you"
    CATEGORY_TRENDING = "trending"
    CATEGORY_COURSE = "course_based"
    CATEGORY_RELATED = "related"
    CATEGORY_DOWNLOAD = "download_based"
    CATEGORY_SAVED = "saved_based"

    CATEGORY_CHOICES = [
        (CATEGORY_FOR_YOU, "For You"),
        (CATEGORY_TRENDING, "Trending"),
        (CATEGORY_COURSE, "Course Based"),
        (CATEGORY_RELATED, "Related"),
        (CATEGORY_DOWNLOAD, "Download Based"),
        (CATEGORY_SAVED, "Saved Based"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_cache",
    )
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="recommendation_cache_rows",
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    score = models.FloatField(default=0.0)
    reason = models.CharField(max_length=255, blank=True)
    rank = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "Recommendation Cache"
        verbose_name_plural = "Recommendation Cache"
        unique_together = ["user", "resource", "category"]
        ordering = ["category", "rank"]
        indexes = [
            models.Index(fields=["user", "category", "expires_at"]),
            models.Index(fields=["resource", "category"]),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.resource_id} ({self.category})"
