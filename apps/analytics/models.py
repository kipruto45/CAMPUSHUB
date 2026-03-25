"""
Analytics models for event tracking and user analytics.
"""

import uuid
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AnalyticsEvent(TimeStampedModel):
    """
    Track user events for analytics.
    """
    
    EVENT_TYPES = [
        ("page_view", "Page View"),
        ("resource_view", "Resource View"),
        ("resource_download", "Resource Download"),
        ("resource_upload", "Resource Upload"),
        ("search", "Search"),
        ("bookmark", "Bookmark"),
        ("favorite", "Favorite"),
        ("comment", "Comment"),
        ("rating", "Rating"),
        ("share", "Share"),
        ("signup", "Signup"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("subscription", "Subscription"),
        ("payment", "Payment"),
        ("chat_message", "Chat Message"),
        ("study_group_join", "Study Group Join"),
        ("notification_click", "Notification Click"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User (optional - some events may be anonymous)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_events"
    )
    session_id = models.CharField(max_length=100, blank=True)
    
    # Event details
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    event_name = models.CharField(max_length=100)
    
    # Context
    resource_id = models.UUIDField(null=True, blank=True)
    course_id = models.UUIDField(null=True, blank=True)
    unit_id = models.UUIDField(null=True, blank=True)
    
    # Properties (JSON for flexible data)
    properties = models.JSONField(default=dict, blank=True)
    
    # Attribution
    referrer = models.URLField(blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    # Device info
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    
    # Location (optional)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Duration (for timed events)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "analytics"
        ordering = ["-timestamp"]
        verbose_name = "Analytics Event"
        verbose_name_plural = "Analytics Events"
        indexes = [
            models.Index(fields=["user", "event_type", "-timestamp"]),
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["resource_id", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.event_name}"


class DailyMetric(TimeStampedModel):
    """
    Daily aggregated metrics for quick dashboards.
    """
    
    date = models.DateField(unique=True, db_index=True)
    
    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    new_signups = models.PositiveIntegerField(default=0)
    active_dau = models.PositiveIntegerField(default=0)  # Daily active users
    active_wau = models.PositiveIntegerField(default=0)  # Weekly active users
    active_mau = models.PositiveIntegerField(default=0)  # Monthly active users
    
    # Content metrics
    total_resources = models.PositiveIntegerField(default=0)
    new_resources = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)
    
    # Engagement
    total_bookmarks = models.PositiveIntegerField(default=0)
    total_favorites = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)
    total_ratings = models.PositiveIntegerField(default=0)
    total_shares = models.PositiveIntegerField(default=0)
    
    # Social
    new_friendships = models.PositiveIntegerField(default=0)
    study_groups_created = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    
    # Revenue
    new_subscriptions = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Storage
    total_storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = "analytics"
        ordering = ["-date"]
        verbose_name = "Daily Metric"
        verbose_name_plural = "Daily Metrics"

    def __str__(self):
        return f"Metrics for {self.date}"


# Backward compatibility for legacy imports/tests that still reference
# DailyAnalytics after the model was superseded by DailyMetric.
DailyAnalytics = DailyMetric


class Cohort(TimeStampedModel):
    """
    User cohort tracking for retention analysis.
    """
    
    cohort_date = models.DateField(db_index=True)
    cohort_type = models.CharField(max_length=50)  # signup, first_action, subscription
    
    # Period metrics (period 0 = cohort start, period 1 = after 1 period, etc.)
    # Stored as JSON for flexibility
    retention_data = models.JSONField(default=dict)
    
    # Summary
    initial_users = models.PositiveIntegerField(default=0)
    total_retained = models.PositiveIntegerField(default=0)
    retention_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        app_label = "analytics"
        unique_together = ["cohort_date", "cohort_type"]
        ordering = ["-cohort_date"]
        verbose_name = "Cohort"
        verbose_name_plural = "Cohorts"

    def __str__(self):
        return f"{self.cohort_type} - {self.cohort_date}"


class UserActivitySummary(TimeStampedModel):
    """
    Periodic user activity summary for quick lookups.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_summaries"
    )
    
    period_start = models.DateField()
    period_end = models.DateField()
    period_type = models.CharField(max_length=20)  # daily, weekly, monthly
    
    # Activity counts
    page_views = models.PositiveIntegerField(default=0)
    resource_views = models.PositiveIntegerField(default=0)
    downloads = models.PositiveIntegerField(default=0)
    uploads = models.PositiveIntegerField(default=0)
    searches = models.PositiveIntegerField(default=0)
    bookmarks = models.PositiveIntegerField(default=0)
    favorites = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    ratings = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    
    # Time spent (seconds)
    total_active_seconds = models.PositiveIntegerField(default=0)
    
    # Streak
    current_streak_days = models.PositiveIntegerField(default=0)
    longest_streak_days = models.PositiveIntegerField(default=0)
    
    # Last activity
    last_active = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "analytics"
        unique_together = ["user", "period_start", "period_type"]
        ordering = ["-period_start"]
        verbose_name = "User Activity Summary"
        verbose_name_plural = "User Activity Summaries"

    def __str__(self):
        return f"{self.user.username} - {self.period_start}"


class LearningInsight(TimeStampedModel):
    """
    AI-generated learning insights for students.
    """
    
    INSIGHT_TYPES = [
        ("study_pattern", "Study Pattern"),
        ("resource_gap", "Resource Gap"),
        ("engagement_drop", "Engagement Drop"),
        ("progress", "Progress"),
        ("recommendation", "Recommendation"),
        ("alert", "Alert"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_insights"
    )
    
    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Related entities
    course_id = models.UUIDField(null=True, blank=True)
    unit_id = models.UUIDField(null=True, blank=True)
    
    # Priority/severity
    priority = models.CharField(max_length=20, default="medium")  # low, medium, high
    
    # Action
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=100, blank=True)
    
    # Metadata
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "analytics"
        ordering = ["-created_at"]
        verbose_name = "Learning Insight"
        verbose_name_plural = "Learning Insights"

    def __str__(self):
        return f"{self.insight_type}: {self.title}"


class RiskLevel:
    """Risk level constants for at-risk students."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    CHOICES = [
        (LOW, "Low Risk"),
        (MEDIUM, "Medium Risk"),
        (HIGH, "High Risk"),
        (CRITICAL, "Critical Risk"),
    ]


class StudentRiskAssessment(TimeStampedModel):
    """
    Track student risk assessments for early warning system.
    """
    
    RISK_CATEGORIES = [
        ("academic", "Academic Performance"),
        ("engagement", "Engagement"),
        ("attendance", "Attendance"),
        ("behavioral", "Behavioral"),
        ("overall", "Overall Risk"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="risk_assessments"
    )
    
    # Risk assessment details
    risk_level = models.CharField(max_length=20, choices=RiskLevel.CHOICES, default=RiskLevel.LOW)
    risk_category = models.CharField(max_length=30, choices=RISK_CATEGORIES, default="overall")
    risk_score = models.FloatField(default=0.0)  # 0-100 scale
    
    # Risk factors contributing to this assessment
    risk_factors = models.JSONField(default=dict, blank=True)
    
    # Assessment metadata
    assessment_date = models.DateField(auto_now_add=True)
    previous_risk_level = models.CharField(max_length=20, choices=RiskLevel.CHOICES, null=True, blank=True)
    risk_change = models.CharField(max_length=20, blank=True)  # increased, decreased, stable
    
    # Related course/unit (optional)
    course_id = models.UUIDField(null=True, blank=True)
    unit_id = models.UUIDField(null=True, blank=True)
    
    # Intervention recommendations
    recommendations = models.JSONField(default=list, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    alert_sent = models.BooleanField(default=False)
    alert_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = "analytics"
        ordering = ["-assessment_date"]
        verbose_name = "Student Risk Assessment"
        verbose_name_plural = "Student Risk Assessments"
        indexes = [
            models.Index(fields=["user", "risk_level", "-assessment_date"]),
            models.Index(fields=["risk_level", "-assessment_date"]),
            models.Index(fields=["alert_sent", "-assessment_date"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.risk_level} risk ({self.assessment_date})"
