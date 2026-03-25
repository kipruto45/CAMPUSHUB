"""
Models for Google Classroom integration.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class GoogleClassroomAccount(TimeStampedModel):
    """
    Model to store Google Classroom OAuth credentials and account info.
    """

    class SyncStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SYNCING = "syncing", "Syncing"
        ERROR = "error", "Error"
        DISCONNECTED = "disconnected", "Disconnected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_classroom_account",
    )
    google_user_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255)
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expires_at = models.DateTimeField()
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.ACTIVE,
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Google Classroom Account"
        verbose_name_plural = "Google Classroom Accounts"

    def __str__(self):
        return f"{self.email} - Google Classroom"


class SyncedCourse(TimeStampedModel):
    """
    Model to map Google Classroom courses to CampusHub units.
    """

    account = models.ForeignKey(
        GoogleClassroomAccount,
        on_delete=models.CASCADE,
        related_name="synced_courses",
    )
    google_course_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    section = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    room = models.CharField(max_length=255, blank=True)
    owner_id = models.CharField(max_length=255, blank=True)
    enrollment_code = models.CharField(max_length=255, blank=True)
    # Optional link to CampusHub unit if manually linked
    linked_unit = models.ForeignKey(
        "courses.Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="google_classroom_links",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Course"
        verbose_name_plural = "Synced Courses"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.google_course_id})"


class SyncedAssignment(TimeStampedModel):
    """
    Model to store synced assignments from Google Classroom.
    """

    class AssignmentState(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        DELETED = "deleted", "Deleted"

    synced_course = models.ForeignKey(
        SyncedCourse,
        on_delete=models.CASCADE,
        related_name="synced_assignments",
    )
    google_assignment_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    state = models.CharField(
        max_length=20,
        choices=AssignmentState.choices,
        default=AssignmentState.DRAFT,
    )
    due_date = models.DateTimeField(null=True, blank=True)
    max_points = models.FloatField(null=True, blank=True)
    work_type = models.CharField(max_length=50, blank=True)
    alternate_link = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Assignment"
        verbose_name_plural = "Synced Assignments"
        ordering = ["-due_date", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.google_assignment_id})"


class SyncedSubmission(TimeStampedModel):
    """
    Model to store student submissions from Google Classroom.
    """

    class SubmissionState(models.TextChoices):
        CREATED = "created", "Created"
        TURNED_IN = "turned_in", "Turned In"
        RETURNED = "returned", "Returned"
        RECLAIMED_BY_STUDENT = "reclaimed_by_student", "Reclaimed by Student"
        MISSING = "missing", "Missing"

    synced_assignment = models.ForeignKey(
        SyncedAssignment,
        on_delete=models.CASCADE,
        related_name="synced_submissions",
    )
    google_submission_id = models.CharField(max_length=255, unique=True)
    student_email = models.EmailField()
    state = models.CharField(
        max_length=30,
        choices=SubmissionState.choices,
        default=SubmissionState.CREATED,
    )
    assigned_grade = models.FloatField(null=True, blank=True)
    draft_grade = models.FloatField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Submission"
        verbose_name_plural = "Synced Submissions"
        unique_together = ["synced_assignment", "student_email"]

    def __str__(self):
        return f"{self.student_email} - {self.synced_assignment.title}"


class SyncedAnnouncement(TimeStampedModel):
    """
    Model to store synced announcements from Google Classroom.
    """

    synced_course = models.ForeignKey(
        SyncedCourse,
        on_delete=models.CASCADE,
        related_name="synced_announcements",
    )
    google_announcement_id = models.CharField(max_length=255, unique=True)
    text = models.TextField()
    state = models.CharField(max_length=20, default="published")
    scheduled_date = models.DateTimeField(null=True, blank=True)
    alternate_link = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Announcement"
        verbose_name_plural = "Synced Announcements"
        ordering = ["-scheduled_date", "-created_at"]

    def __str__(self):
        return f"{self.text[:50]}... ({self.google_announcement_id})"


class SyncState(TimeStampedModel):
    """
    Model to track sync state and history.
    """

    class SyncType(models.TextChoices):
        FULL = "full", "Full Sync"
        INCREMENTAL = "incremental", "Incremental Sync"
        MANUAL = "manual", "Manual Sync"
        SCHEDULED = "scheduled", "Scheduled Sync"

    class SyncResult(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PARTIAL = "partial", "Partial"

    account = models.ForeignKey(
        GoogleClassroomAccount,
        on_delete=models.CASCADE,
        related_name="sync_history",
    )
    sync_type = models.CharField(max_length=20, choices=SyncType.choices)
    result = models.CharField(max_length=20, choices=SyncResult.choices)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    courses_count = models.PositiveIntegerField(default=0)
    assignments_count = models.PositiveIntegerField(default=0)
    announcements_count = models.PositiveIntegerField(default=0)
    submissions_count = models.PositiveIntegerField(default=0)
    errors = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sync State"
        verbose_name_plural = "Sync States"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.sync_type} - {self.result} ({self.started_at})"
