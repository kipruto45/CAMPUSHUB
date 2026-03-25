"""
Models for Microsoft Teams integration.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class MicrosoftTeamsAccount(TimeStampedModel):
    """
    Model to store Microsoft Teams OAuth credentials and account info.
    """

    class SyncStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SYNCING = "syncing", "Syncing"
        ERROR = "error", "Error"
        DISCONNECTED = "disconnected", "Disconnected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="microsoft_teams_account",
    )
    microsoft_user_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
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
        verbose_name = "Microsoft Teams Account"
        verbose_name_plural = "Microsoft Teams Accounts"

    def __str__(self):
        return f"{self.email} - Microsoft Teams"


class SyncedTeam(TimeStampedModel):
    """
    Model to map Microsoft Teams to CampusHub units.
    """

    account = models.ForeignKey(
        MicrosoftTeamsAccount,
        on_delete=models.CASCADE,
        related_name="synced_teams",
    )
    team_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=50, blank=True)
    owner_id = models.CharField(max_length=255, blank=True)
    # Optional link to CampusHub unit if manually linked
    linked_unit = models.ForeignKey(
        "courses.Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="microsoft_teams_links",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Team"
        verbose_name_plural = "Synced Teams"
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.display_name} ({self.team_id})"


class SyncedChannel(TimeStampedModel):
    """
    Model to store synced channels from Microsoft Teams.
    """

    synced_team = models.ForeignKey(
        SyncedTeam,
        on_delete=models.CASCADE,
        related_name="synced_channels",
    )
    channel_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_general = models.BooleanField(default=False)
    web_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Channel"
        verbose_name_plural = "Synced Channels"
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.display_name} ({self.channel_id})"


class SyncedAssignment(TimeStampedModel):
    """
    Model to store synced assignments from Microsoft Teams.
    """

    class AssignmentStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        DELETED = "deleted", "Deleted"

    synced_team = models.ForeignKey(
        SyncedTeam,
        on_delete=models.CASCADE,
        related_name="synced_assignments",
    )
    assignment_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.DRAFT,
    )
    due_date_time = models.DateTimeField(null=True, blank=True)
    due_date_includes_time = models.BooleanField(default=True)
    grading_type = models.CharField(max_length=50, blank=True)
    max_points = models.FloatField(null=True, blank=True)
    web_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Assignment"
        verbose_name_plural = "Synced Assignments"
        ordering = ["-due_date_time", "-created_at"]

    def __str__(self):
        return f"{self.display_name} ({self.assignment_id})"


class SyncedSubmission(TimeStampedModel):
    """
    Model to store student submissions from Microsoft Teams.
    """

    class SubmissionState(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        WORKING_ON_IT = "working_on_it", "Working On It"
        SUBMITTED = "submitted", "Submitted"
        RETURNED = "returned", "Returned"

    synced_assignment = models.ForeignKey(
        SyncedAssignment,
        on_delete=models.CASCADE,
        related_name="synced_submissions",
    )
    submission_id = models.CharField(max_length=255, unique=True)
    student_email = models.EmailField()
    state = models.CharField(
        max_length=30,
        choices=SubmissionState.choices,
        default=SubmissionState.NOT_STARTED,
    )
    grade = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Submission"
        verbose_name_plural = "Synced Submissions"
        unique_together = ["synced_assignment", "student_email"]

    def __str__(self):
        return f"{self.student_email} - {self.synced_assignment.display_name}"


class SyncedAnnouncement(TimeStampedModel):
    """
    Model to store synced announcements from Microsoft Teams.
    """

    synced_channel = models.ForeignKey(
        SyncedChannel,
        on_delete=models.CASCADE,
        related_name="synced_announcements",
    )
    announcement_id = models.CharField(max_length=255, unique=True)
    topic = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    is_pinned = models.BooleanField(default=False)
    web_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Synced Announcement"
        verbose_name_plural = "Synced Announcements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.topic[:50]}... ({self.announcement_id})"


class SyncState(TimeStampedModel):
    """
    Model to track sync state and history.
    """

    class SyncType(models.TextChoices):
        FULL = "full", "Full Sync"
        INCREMENTAL = "incremental", "Incremental Sync"
        MANUAL = "manual", "Manual Sync"

    class SyncResult(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PARTIAL = "partial", "Partial"

    account = models.ForeignKey(
        MicrosoftTeamsAccount,
        on_delete=models.CASCADE,
        related_name="sync_history",
    )
    sync_type = models.CharField(max_length=20, choices=SyncType.choices)
    result = models.CharField(max_length=20, choices=SyncResult.choices)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    teams_count = models.PositiveIntegerField(default=0)
    channels_count = models.PositiveIntegerField(default=0)
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