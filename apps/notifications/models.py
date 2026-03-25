"""
Models for notifications app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class NotificationType:
    """Notification type constants."""

    # User notifications
    RESOURCE_APPROVED = "resource_approved"
    RESOURCE_REJECTED = "resource_rejected"
    NEW_RESOURCE = "new_resource"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_LIKED = "resource_liked"
    NEW_COMMENT = "new_comment"
    COMMENT_REPLY = "comment_reply"
    NEW_RATING = "new_rating"
    NEW_DOWNLOAD = "new_download"
    TRENDING = "trending"
    ANNOUNCEMENT = "announcement"
    SYSTEM = "system"
    REPORT_UPDATE = "report_update"
    INACTIVITY_REMINDER = "inactivity_reminder"
    RESOURCE_SHARED_WITH_USER = "resource_shared_with_user"
    RESOURCE_SHARED_TO_GROUP = "resource_shared_to_group"
    RESOURCE_REQUEST = "resource_request"

    # Admin notifications
    ADMIN_USER_REPORT = "admin_user_report"
    ADMIN_CONTENT_REPORT = "admin_content_report"
    ADMIN_NEW_USER_SIGNUP = "admin_new_user_signup"
    ADMIN_SUSPICIOUS_ACTIVITY = "admin_suspicious_activity"
    ADMIN_SYSTEM_ALERT = "admin_system_alert"
    ADMIN_RESOURCE_PENDING_MODERATION = "admin_resource_pending_moderation"
    ADMIN_BULK_OPERATION_COMPLETE = "admin_bulk_operation_complete"
    ADMIN_API_THRESHOLD_WARNING = "admin_api_threshold_warning"
    ADMIN_STORAGE_WARNING = "admin_storage_warning"
    ADMIN_PERFORMANCE_ALERT = "admin_performance_alert"
    
    # At-risk student notifications
    STUDENT_AT_RISK = "student_at_risk"
    STUDENT_RISK_INCREASED = "student_risk_increased"
    STUDENT_RISK_CRITICAL = "student_risk_critical"
    ADVISOR_STUDENT_AT_RISK = "advisor_student_at_risk"
    INSTRUCTOR_STUDENT_AT_RISK = "instructor_student_at_risk"

    CHOICES = [
        (RESOURCE_APPROVED, "Resource Approved"),
        (RESOURCE_REJECTED, "Resource Rejected"),
        (NEW_RESOURCE, "New Resource"),
        (RESOURCE_UPDATED, "Resource Updated"),
        (RESOURCE_LIKED, "Resource Liked"),
        (NEW_COMMENT, "New Comment"),
        (COMMENT_REPLY, "Comment Reply"),
        (NEW_RATING, "New Rating"),
        (NEW_DOWNLOAD, "New Download"),
        (TRENDING, "Trending Resource"),
        (ANNOUNCEMENT, "Announcement"),
        (REPORT_UPDATE, "Report Update"),
        (RESOURCE_SHARED_WITH_USER, "Resource Shared With User"),
        (RESOURCE_SHARED_TO_GROUP, "Resource Shared To Group"),
        (RESOURCE_REQUEST, "Resource Request"),
        (INACTIVITY_REMINDER, "Engagement Reminder"),
        (SYSTEM, "System Notification"),
        # Admin notification types
        (ADMIN_USER_REPORT, "Admin: User Report Received"),
        (ADMIN_CONTENT_REPORT, "Admin: Content Report Received"),
        (ADMIN_NEW_USER_SIGNUP, "Admin: New User Signup"),
        (ADMIN_SUSPICIOUS_ACTIVITY, "Admin: Suspicious Activity Detected"),
        (ADMIN_SYSTEM_ALERT, "Admin: System Alert"),
        (ADMIN_RESOURCE_PENDING_MODERATION, "Admin: Resource Pending Moderation"),
        (ADMIN_BULK_OPERATION_COMPLETE, "Admin: Bulk Operation Complete"),
        (ADMIN_API_THRESHOLD_WARNING, "Admin: API Threshold Warning"),
        (ADMIN_STORAGE_WARNING, "Admin: Storage Warning"),
        (ADMIN_PERFORMANCE_ALERT, "Admin: Performance Alert"),
    
    # At-risk student notification types
    (STUDENT_AT_RISK, "Student At Risk"),
    (STUDENT_RISK_INCREASED, "Student Risk Increased"),
    (STUDENT_RISK_CRITICAL, "Student Risk Critical"),
    (ADVISOR_STUDENT_AT_RISK, "Advisor: Student At Risk"),
    (INSTRUCTOR_STUDENT_AT_RISK, "Instructor: Student At Risk"),
    ]


class NotificationPriority:
    """Notification priority constants."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    CHOICES = [
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (URGENT, "Urgent"),
    ]


class Notification(TimeStampedModel):
    """Model for notifications."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50, choices=NotificationType.CHOICES, default=NotificationType.SYSTEM
    )
    priority = models.CharField(
        max_length=20, choices=NotificationPriority.CHOICES, default=NotificationPriority.MEDIUM
    )
    is_read = models.BooleanField(default=False)
    is_admin_notification = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True)

    # Optional target references for richer data
    target_resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    target_comment = models.ForeignKey(
        "comments.Comment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.email} - {self.title}"

    @property
    def notification_type_display(self):
        """Get human-readable notification type."""
        return self.get_notification_type_display()


class DeviceToken(TimeStampedModel):
    """Model for storing device tokens for push notifications."""

    DEVICE_TYPE_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    device_token = models.CharField(max_length=500, unique=True)
    device_type = models.CharField(
        max_length=20, choices=DEVICE_TYPE_CHOICES, default="android"
    )
    device_name = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Device Token"
        verbose_name_plural = "Device Tokens"
        ordering = ["-last_used"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["device_token"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_type}"
