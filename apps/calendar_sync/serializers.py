"""
Serializers for Calendar Sync
"""

from rest_framework import serializers
from .models import CalendarAccount, SyncedEvent, SyncSettings


class CalendarAccountSerializer(serializers.ModelSerializer):
    """Serializer for CalendarAccount"""
    
    class Meta:
        model = CalendarAccount
        fields = [
            'id', 'provider', 'email', 'sync_enabled',
            'last_sync_at', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_sync_at', 'created_at', 'updated_at']


class SyncedEventSerializer(serializers.ModelSerializer):
    """Serializer for SyncedEvent"""
    
    class Meta:
        model = SyncedEvent
        fields = [
            'id', 'external_event_id', 'title', 'description',
            'start_time', 'end_time', 'location', 'is_all_day',
            'attendees', 'last_synced_at', 'is_deleted',
        ]
        read_only_fields = ['id', 'last_synced_at']


class SyncSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SyncSettings"""
    
    class Meta:
        model = SyncSettings
        fields = [
            'id', 'auto_sync', 'sync_interval_minutes', 'sync_direction',
            'sync_lectures', 'sync_assignments', 'sync_exams',
            'sync_study_sessions', 'sync_personal',
            'notify_before_events', 'notify_minutes_before',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
