"""
Models for Learning Analytics
Tracks student learning patterns, progress, and performance
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class LearningSession(models.Model):
    """Track individual learning sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_sessions'
    )
    subject = models.CharField(max_length=255, blank=True)
    resource = models.ForeignKey(
        'resources.Resource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='learning_sessions'
    )
    session_type = models.CharField(
        max_length=50,
        choices=[
            ('study', 'Study Session'),
            ('reading', 'Reading'),
            ('video', 'Video Watching'),
            ('practice', 'Practice'),
            ('quiz', 'Quiz'),
            ('review', 'Review'),
        ]
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=0)
    pages_viewed = models.IntegerField(default=0)
    interactions = models.IntegerField(default=0)
    
    # Engagement metrics
    focus_score = models.FloatField(default=0.0)  # 0-100
    completion_rate = models.FloatField(default=0.0)  # 0-100
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'started_at']),
            models.Index(fields=['subject']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.session_type} - {self.started_at}"
    
    def end_session(self):
        """End the session and calculate duration"""
        self.ended_at = timezone.now()
        if self.started_at:
            delta = self.ended_at - self.started_at
            self.duration_minutes = int(delta.total_seconds() / 60)
        self.save()


class LearningProgress(models.Model):
    """Track progress through courses and materials"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_progress'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='learning_progress'
    )
    resource = models.ForeignKey(
        'resources.Resource',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='learning_progress'
    )
    
    # Progress tracking
    progress_percentage = models.FloatField(default=0.0)  # 0-100
    time_spent_minutes = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Mastery metrics
    mastery_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('mastered', 'Mastered'),
        ],
        default='beginner'
    )
    quiz_score = models.FloatField(null=True, blank=True)
    attempts_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_accessed']
        unique_together = ['user', 'course', 'resource']
        indexes = [
            models.Index(fields=['user', 'completed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.progress_percentage}% complete"


class StudyStreak(models.Model):
    """Track daily study streaks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_streaks'
    )
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_study_date = models.DateField(null=True, blank=True)
    total_study_days = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Study streaks'
    
    def __str__(self):
        return f"{self.user.email} - {self.current_streak} day streak"
    
    def update_streak(self):
        """Update streak based on today's activity"""
        today = timezone.now().date()
        
        if self.last_study_date == today:
            # Already studied today, no update needed
            return
        
        if self.last_study_date == today - timezone.timedelta(days=1):
            # Consecutive day - increment streak
            self.current_streak += 1
        elif self.last_study_date != today:
            # Streak broken - reset to 1
            self.current_streak = 1
        
        self.last_study_date = today
        self.total_study_days += 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.save()


class LearningInsight(models.Model):
    """AI-generated learning insights and recommendations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_analytics_insights'
    )
    
    INSIGHT_TYPES = [
        ('strength', 'Strength'),
        ('weakness', 'Weakness'),
        ('recommendation', 'Recommendation'),
        ('achievement', 'Achievement'),
        ('suggestion', 'Study Suggestion'),
    ]
    
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    subject = models.CharField(max_length=255, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium'
    )
    is_read = models.BooleanField(default=False)
    is_actioned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.insight_type}: {self.title}"


class PerformanceMetrics(models.Model):
    """Aggregated performance metrics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_metrics'
    )
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Study metrics
    total_study_time_minutes = models.IntegerField(default=0)
    sessions_count = models.IntegerField(default=0)
    average_session_duration = models.FloatField(default=0.0)
    
    # Progress metrics
    resources_completed = models.IntegerField(default=0)
    courses_enrolled = models.IntegerField(default=0)
    courses_completed = models.IntegerField(default=0)
    
    # Performance metrics
    average_quiz_score = models.FloatField(null=True, blank=True)
    average_mastery_level = models.FloatField(default=0.0)
    
    # Engagement metrics
    login_frequency = models.IntegerField(default=0)
    active_days = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'period_start', 'period_end']
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.user.email} - {self.period_start} to {self.period_end}"
