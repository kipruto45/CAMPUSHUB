"""
Serializers for Learning Analytics
"""

from rest_framework import serializers
from .models import LearningSession, LearningProgress, StudyStreak, LearningInsight, PerformanceMetrics


class LearningSessionSerializer(serializers.ModelSerializer):
    """Serializer for LearningSession"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = LearningSession
        fields = [
            'id', 'user', 'user_email', 'subject', 'resource', 'session_type',
            'started_at', 'ended_at', 'duration_minutes', 'pages_viewed',
            'interactions', 'focus_score', 'completion_rate', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class LearningProgressSerializer(serializers.ModelSerializer):
    """Serializer for LearningProgress"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = LearningProgress
        fields = [
            'id', 'user', 'user_email', 'course', 'resource',
            'progress_percentage', 'time_spent_minutes', 'last_accessed',
            'completed_at', 'mastery_level', 'quiz_score', 'attempts_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StudyStreakSerializer(serializers.ModelSerializer):
    """Serializer for StudyStreak"""
    
    class Meta:
        model = StudyStreak
        fields = [
            'id', 'user', 'current_streak', 'longest_streak',
            'last_study_date', 'total_study_days', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class LearningInsightSerializer(serializers.ModelSerializer):
    """Serializer for LearningInsight"""
    
    class Meta:
        model = LearningInsight
        fields = [
            'id', 'user', 'insight_type', 'title', 'description',
            'subject', 'priority', 'is_read', 'is_actioned',
            'created_at', 'expires_at',
        ]
        read_only_fields = ['id', 'created_at']


class PerformanceMetricsSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceMetrics"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = PerformanceMetrics
        fields = [
            'id', 'user', 'user_email', 'period_start', 'period_end',
            'total_study_time_minutes', 'sessions_count', 'average_session_duration',
            'resources_completed', 'courses_enrolled', 'courses_completed',
            'average_quiz_score', 'average_mastery_level',
            'login_frequency', 'active_days', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
