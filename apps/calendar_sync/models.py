"""
Models for Calendar Sync
Stores calendar connection info and synced events
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class CalendarAccount(models.Model):
    """Stores user's connected calendar accounts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_accounts'
    )
    
    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Outlook Calendar'),
        ('apple', 'Apple Calendar'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    email = models.EmailField()
    
    # OAuth tokens (encrypted in production)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Calendar settings
    calendar_id = models.CharField(max_length=255, blank=True)  # Primary calendar ID
    sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'provider', 'email']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.provider} ({self.email})"
    
    def is_token_expired(self):
        """Check if the access token is expired"""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at


class SyncedEvent(models.Model):
    """Stores events synced from external calendars"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar_account = models.ForeignKey(
        CalendarAccount,
        on_delete=models.CASCADE,
        related_name='synced_events'
    )
    
    # External event ID from the provider
    external_event_id = models.CharField(max_length=255)
    
    # Event details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    is_all_day = models.BooleanField(default=False)
    
    # Attendees (stored as JSON)
    attendees = models.JSONField(default=list)
    
    # Sync metadata
    last_synced_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['calendar_account', 'external_event_id']
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['calendar_account', 'start_time']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_time}"


class SyncSettings(models.Model):
    """User-specific sync settings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_sync_settings'
    )
    
    # Sync preferences
    auto_sync = models.BooleanField(default=True)
    sync_interval_minutes = models.IntegerField(default=30)
    sync_direction = models.CharField(
        max_length=20,
        choices=[
            ('import', 'Import only'),
            ('export', 'Export only'),
            ('bidirectional', 'Bidirectional'),
        ],
        default='bidirectional'
    )
    
    # What to sync
    sync_lectures = models.BooleanField(default=True)
    sync_assignments = models.BooleanField(default=True)
    sync_exams = models.BooleanField(default=True)
    sync_study_sessions = models.BooleanField(default=True)
    sync_personal = models.BooleanField(default=True)
    
    # Notifications
    notify_before_events = models.BooleanField(default=True)
    notify_minutes_before = models.IntegerField(default=15)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Sync settings for {self.user.email}"
