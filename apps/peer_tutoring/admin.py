"""
Admin configuration for Peer Tutoring
"""

from django.contrib import admin
from .models import TutoringProfile, TutoringSession, TutoringRequest, TutoringReview, TutoringSubject


@admin.register(TutoringProfile)
class TutoringProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_available', 'hourly_rate', 'total_sessions', 'average_rating', 'is_verified']
    list_filter = ['is_available', 'is_verified']
    search_fields = ['user__email']
    raw_id_fields = ['user']


@admin.register(TutoringSession)
class TutoringSessionAdmin(admin.ModelAdmin):
    list_display = ['subject', 'tutor', 'student', 'status', 'scheduled_start']
    list_filter = ['status', 'scheduled_start']
    search_fields = ['subject', 'tutor__user__email', 'student__email']
    raw_id_fields = ['tutor', 'student']


@admin.register(TutoringRequest)
class TutoringRequestAdmin(admin.ModelAdmin):
    list_display = ['subject', 'student', 'status', 'expires_at']
    list_filter = ['status']
    search_fields = ['subject', 'student__email']
    raw_id_fields = ['student']


@admin.register(TutoringReview)
class TutoringReviewAdmin(admin.ModelAdmin):
    list_display = ['tutor', 'reviewer', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    raw_id_fields = ['session', 'reviewer', 'tutor']


@admin.register(TutoringSubject)
class TutoringSubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'is_active']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'code']
