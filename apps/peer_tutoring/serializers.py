"""
Serializers for Peer Tutoring
"""

from rest_framework import serializers
from .models import TutoringProfile, TutoringSession, TutoringRequest, TutoringReview, TutoringSubject


class TutoringProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.URLField(source='user.avatar_url', read_only=True)
    
    class Meta:
        model = TutoringProfile
        fields = [
            'id', 'user', 'user_name', 'user_avatar', 'is_available',
            'hourly_rate', 'bio', 'expertise', 'experience_years',
            'total_sessions', 'total_hours', 'average_rating', 'total_reviews',
            'is_verified', 'created_at',
        ]


class TutoringSessionSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source='tutor.user.get_full_name', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    
    class Meta:
        model = TutoringSession
        fields = [
            'id', 'tutor', 'tutor_name', 'student', 'student_name',
            'subject', 'topic', 'description', 'scheduled_start', 'scheduled_end',
            'actual_start', 'actual_end', 'status', 'video_link', 'location',
            'rate', 'is_paid', 'duration_minutes', 'created_at',
        ]


class TutoringRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    
    class Meta:
        model = TutoringRequest
        fields = [
            'id', 'student', 'student_name', 'subject', 'topic', 'description',
            'preferred_rate_max', 'status', 'expires_at', 'created_at',
        ]


class TutoringReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    
    class Meta:
        model = TutoringReview
        fields = [
            'id', 'session', 'reviewer', 'reviewer_name', 'tutor',
            'rating', 'comment', 'knowledge_rating', 'communication_rating',
            'patience_rating', 'is_public', 'created_at',
        ]


class TutoringSubjectSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = TutoringSubject
        fields = ['id', 'name', 'code', 'description', 'category', 'is_active']
