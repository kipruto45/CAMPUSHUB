"""Database models for analytics snapshots."""

from django.db import models


class DailyAnalytics(models.Model):
    """Daily platform snapshot for trend reporting."""

    date = models.DateField(unique=True, db_index=True)
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    total_resources = models.PositiveIntegerField(default=0)
    approved_resources = models.PositiveIntegerField(default=0)
    pending_resources = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Daily Analytics Snapshot"
        verbose_name_plural = "Daily Analytics Snapshots"
        ordering = ["-date"]

    def __str__(self):
        return f"Analytics snapshot for {self.date}"
