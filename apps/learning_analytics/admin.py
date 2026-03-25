"""
Admin configuration for Learning Analytics
"""

from django.contrib import admin
from .models import LearningSession, LearningProgress, StudyStreak, LearningInsight, PerformanceMetrics


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_type', 'subject', 'duration_minutes', 'started_at']
    list_filter = ['session_type', 'started_at']
    search_fields = ['user__email', 'subject']
    raw_id_fields = ['user', 'resource']
    readonly_fields = ['created_at']


@admin.register(LearningProgress)
class LearningProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'progress_percentage', 'mastery_level', 'completed_at', 'last_accessed']
    list_filter = ['mastery_level', 'completed_at']
    search_fields = ['user__email']
    raw_id_fields = ['user', 'course', 'resource']


@admin.register(StudyStreak)
class StudyStreakAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_streak', 'longest_streak', 'total_study_days', 'last_study_date']
    search_fields = ['user__email']
    raw_id_fields = ['user']


@admin.register(LearningInsight)
class LearningInsightAdmin(admin.ModelAdmin):
    list_display = ['user', 'insight_type', 'title', 'priority', 'is_read', 'created_at']
    list_filter = ['insight_type', 'priority', 'is_read', 'created_at']
    search_fields = ['user__email', 'title']
    raw_id_fields = ['user']


@admin.register(PerformanceMetrics)
class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'period_start', 'period_end', 'total_study_time_minutes', 'sessions_count']
    list_filter = ['period_start', 'period_end']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    readonly_fields = ['created_at']
