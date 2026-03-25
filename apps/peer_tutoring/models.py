"""
Models for Peer Tutoring
Student-tutor matching and session management
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class TutoringProfile(models.Model):
    """Extended profile for students who want to tutor"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tutoring_profile'
    )
    
    # Availability
    is_available = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="0 for free tutoring"
    )
    
    # Bio and expertise
    bio = models.TextField(blank=True)
    expertise = models.JSONField(
        default=list,
        help_text="List of subjects/expertise areas"
    )
    experience_years = models.IntegerField(default=0)
    
    # Stats
    total_sessions = models.IntegerField(default=0)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.IntegerField(default=0)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Tutoring profile: {self.user.email}"


class TutoringSession(models.Model):
    """A tutoring session between tutor and student"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    tutor = models.ForeignKey(
        TutoringProfile,
        on_delete=models.CASCADE,
        related_name='tutoring_sessions'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tutoring_sessions_as_student'
    )
    
    # Session details
    subject = models.CharField(max_length=255)
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    # Schedule
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Location (video link or physical)
    video_link = models.URLField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    # Payment
    rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    
    # Notes
    tutor_notes = models.TextField(blank=True)
    student_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_start']
    
    def __str__(self):
        return f"{self.subject} - {self.tutor.user.email} -> {self.student.email}"
    
    @property
    def duration_minutes(self):
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return int(delta.total_seconds() / 60)
        return 0


class TutoringRequest(models.Model):
    """Request for tutoring help"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tutoring_requests'
    )
    
    # Request details
    subject = models.CharField(max_length=255)
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    
    # Preferences
    preferred_rate_max = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0
    )
    preferred_schedule = models.JSONField(default=dict)
    
    # Status
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('matched', 'Matched'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Request: {self.subject} by {self.student.email}"


class TutoringReview(models.Model):
    """Review for a tutoring session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    session = models.OneToOneField(
        TutoringSession,
        on_delete=models.CASCADE,
        related_name='review'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tutoring_reviews_given'
    )
    tutor = models.ForeignKey(
        TutoringProfile,
        on_delete=models.CASCADE,
        related_name='reviews_received'
    )
    
    # Rating (1-5)
    rating = models.IntegerField()
    comment = models.TextField(blank=True)
    
    # Aspects
    knowledge_rating = models.IntegerField(default=5)
    communication_rating = models.IntegerField(default=5)
    patience_rating = models.IntegerField(default=5)
    
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']


class TutoringSubject(models.Model):
    """Available subjects for tutoring"""
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name_plural = 'Tutoring subjects'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
