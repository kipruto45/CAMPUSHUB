"""
Notes Models for CampusHub
Real-time collaborative study notes
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinLengthValidator


class Note(models.Model):
    """Model for collaborative study notes"""
    
    class NoteStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, validators=[MinLengthValidator(1)])
    content = models.TextField(blank=True, default='')
    content_html = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=NoteStatus.choices, default=NoteStatus.DRAFT)
    
    # Owner
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_notes'
    )
    
    # For grouping notes
    folder = models.CharField(max_length=100, blank=True, default='default')
    
    # Tags for organization
    tags = models.JSONField(default=list)
    
    # Real-time collaboration settings
    is_collaborative = models.BooleanField(default=False)
    lock_timeout = models.PositiveIntegerField(default=30)  # seconds
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'study_notes'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['owner', 'folder']),
            models.Index(fields=['status', '-updated_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.owner.username})"
    
    @property
    def collaborators(self):
        """Get all users who have access to this note"""
        from apps.notes.models import NoteShare
        return User.objects.filter(
            note_shares__note=self,
            note_shares__is_active=True
        )
    
    @property
    def version_count(self):
        return self.versions.count()


class NoteShare(models.Model):
    """Model for sharing notes with other users"""
    
    class Permission(models.TextChoices):
        VIEW = 'view', 'View Only'
        EDIT = 'edit', 'Can Edit'
        ADMIN = 'admin', 'Admin'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_shares'
    )
    permission = models.CharField(max_length=20, choices=Permission.choices, default=Permission.VIEW)
    is_active = models.BooleanField(default=True)
    
    # Share settings
    can_share = models.BooleanField(default=False)
    can_copy = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'note_shares'
        unique_together = ['note', 'user']
        indexes = [
            models.Index(fields=['note', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.note.title} -> {self.user.username} ({self.permission})"


class NoteVersion(models.Model):
    """Model for note version history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='versions')
    
    # Version content
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    content_html = models.TextField(blank=True)
    
    # Version metadata
    version_number = models.PositiveIntegerField()
    change_summary = models.CharField(max_length=500, blank=True)
    
    # Who made the change
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='note_versions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'note_versions'
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['note', '-version_number']),
        ]
    
    def __str__(self):
        return f"{self.note.title} v{self.version_number}"


class NotePresence(models.Model):
    """Model for tracking user presence in collaborative editing"""
    
    class ActivityType(models.TextChoices):
        VIEWING = 'viewing', 'Viewing'
        EDITING = 'editing', 'Editing'
        IDLE = 'idle', 'Idle'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='presence')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_presence'
    )
    
    # Presence data
    activity = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.VIEWING)
    cursor_position = models.PositiveIntegerField(default=0)
    cursor_selection = models.JSONField(default=dict)  # {start: int, end: int}
    
    # Last active timestamp
    last_active = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'note_presence'
        unique_together = ['note', 'user']
        indexes = [
            models.Index(fields=['note', 'is_online']),
        ]
    
    def __str__(self):
        return f"{self.user.username} @ {self.note.title} ({self.activity})"


class NoteLock(models.Model):
    """Model for locking notes during editing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='locks')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_locks'
    )
    
    # Lock metadata
    lock_type = models.CharField(max_length=20, default='edit')  # 'edit' or 'view'
    expires_at = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'note_locks'
        indexes = [
            models.Index(fields=['note', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.note.title} locked by {self.user.username}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


# Import User model at module level for backwards compatibility
from django.contrib.auth import get_user_model
User = get_user_model()
