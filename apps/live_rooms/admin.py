"""
Admin configuration for Live Study Rooms
"""

from django.contrib import admin
from .models import StudyRoom, RoomParticipant, RoomMessage, RoomRecording


@admin.register(StudyRoom)
class StudyRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'room_type', 'status', 'is_active', 'is_recording_enabled', 'created_at']
    list_filter = ['room_type', 'status', 'is_recording_enabled', 'created_at']
    search_fields = ['name', 'description', 'host__email']
    readonly_fields = ['created_at', 'started_at', 'ended_at', 'updated_at']
    raw_id_fields = ['host']


@admin.register(RoomParticipant)
class RoomParticipantAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'role', 'status', 'is_active', 'joined_at', 'left_at']
    list_filter = ['status', 'role', 'joined_at']
    search_fields = ['user__email', 'room__name']
    raw_id_fields = ['user', 'room']


@admin.register(RoomMessage)
class RoomMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'message_type', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['user__email', 'room__name', 'content']
    raw_id_fields = ['user', 'room']


@admin.register(RoomRecording)
class RoomRecordingAdmin(admin.ModelAdmin):
    list_display = ['room', 'recorded_by', 'status', 'duration', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['room__name', 'recorded_by__email']
    raw_id_fields = ['room', 'recorded_by']
