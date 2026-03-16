"""Models for search indexing and query history."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class SearchIndex(TimeStampedModel):
    """Denormalized index row for approved public resources."""

    resource = models.OneToOneField(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="search_index",
    )
    search_document = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    indexed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Search Index"
        verbose_name_plural = "Search Index"
        indexes = [
            models.Index(fields=["is_active", "-indexed_at"]),
        ]

    def __str__(self):
        return f"Index for {self.resource_id}"


class RecentSearch(TimeStampedModel):
    """Persisted user-specific recent searches."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recent_searches",
    )
    query = models.CharField(max_length=255)
    normalized_query = models.CharField(max_length=255, db_index=True)
    filters = models.JSONField(default=dict, blank=True)
    results_count = models.PositiveIntegerField(default=0)
    last_searched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Recent Search"
        verbose_name_plural = "Recent Searches"
        ordering = ["-last_searched_at"]
        unique_together = ["user", "normalized_query"]
        indexes = [
            models.Index(fields=["user", "-last_searched_at"]),
            models.Index(fields=["normalized_query", "-last_searched_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.query}"
