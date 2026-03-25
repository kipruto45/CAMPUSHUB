"""
Live Study Rooms Models for CampusHub
WebRTC-based video study session models
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class StudyRoom(models.Model):
    """Model for live study rooms"""
    
    class RoomType(models.TextChoices):
        PUBLIC = 'public', 'Public'
        PRIVATE = 'private', 'Private'
        STUDY_GROUP = 'study_group', 'Study Group'
    
    class RoomStatus(models.TextChoices):
        WAITING = 'waiting', 'Waiting'
        ACTIVE = 'active', 'Active'
        ENDED = 'ended', 'Ended'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.PUBLIC)
    status = models.CharField(max_length=20, choices=RoomStatus.choices, default=RoomStatus.WAITING)
    
    # Host/Owner
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_rooms'
    )
    
    # For study group rooms
    study_group = models.ForeignKey(
        'social.StudyGroup',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='live_rooms'
    )
    
    # Room settings
    max_participants = models.PositiveIntegerField(default=10)
    is_recording_enabled = models.BooleanField(default=False)
    is_screen_share_enabled = models.BooleanField(default=True)
    
    # ICE servers configuration (for WebRTC)
    ice_servers = models.JSONField(default=list)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'live_study_rooms'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    @property
    def is_active(self):
        return self.status == self.RoomStatus.ACTIVE
    
    @property
    def participant_count(self):
        return self.participants.count()
    
    def get_ice_servers(self):
        """Get ICE servers for WebRTC configuration"""
        if self.ice_servers:
            return self.ice_servers
        
        # Default ICE servers (STUN)
        return [
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
        ]


class RoomParticipant(models.Model):
    """Model for room participants"""
    
    class Role(models.TextChoices):
        HOST = 'host', 'Host'
        MODERATOR = 'moderator', 'Moderator'
        PARTICIPANT = 'participant', 'Participant'
    
    class Status(models.TextChoices):
        CONNECTING = 'connecting', 'Connecting'
        CONNECTED = 'connected', 'Connected'
        DISCONNECTED = 'disconnected', 'Disconnected'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        StudyRoom,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_room_participations'
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PARTICIPANT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONNECTING)
    
    # WebRTC connection ID
    peer_id = models.CharField(max_length=100, blank=True)
    
    # Media states
    is_audio_enabled = models.BooleanField(default=True)
    is_video_enabled = models.BooleanField(default=True)
    is_screen_sharing = models.BooleanField(default=False)
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'room_participants'
        unique_together = [['room', 'user']]
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.email} in {self.room.name}"
    
    @property
    def is_active(self):
        return self.status == self.Status.CONNECTED and not self.left_at


class RoomMessage(models.Model):
    """Chat messages in study rooms"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        StudyRoom,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_messages'
    )
    message = models.TextField()
    message_type = models.CharField(max_length=20, default='text')  # text, system
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'room_messages'
        ordering = ['created_at']


class RoomRecording(models.Model):
    """Recording metadata for study rooms"""
    
    class Status(models.TextChoices):
        RECORDING = 'recording', 'Recording'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        StudyRoom,
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_recordings'
    )
    
    # Recording file info
    duration = models.PositiveIntegerField(default=0)  # seconds
    file_size = models.BigIntegerField(default=0)
    file_url = models.URLField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECORDING)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'room_recordings'
        ordering = ['-created_at']
