"""
Serializers for Live Study Rooms
"""

from rest_framework import serializers
from django.utils import timezone
from .models import StudyRoom, RoomParticipant, RoomMessage, RoomRecording


class StudyRoomSerializer(serializers.ModelSerializer):
    """Serializer for StudyRoom model"""
    host_name = serializers.CharField(source='host.get_full_name', read_only=True)
    participant_count = serializers.SerializerMethodField()
    is_joined = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = StudyRoom
        fields = [
            'id',
            'name',
            'description',
            'room_type',
            'status',
            'host',
            'host_name',
            'study_group',
            'max_participants',
            'is_recording_enabled',
            'is_screen_share_enabled',
            'started_at',
            'ended_at',
            'created_at',
            'updated_at',
            'participant_count',
            'is_joined',
            'is_active',
        ]
        read_only_fields = [
            'id',
            'host',
            'created_at',
            'updated_at',
            'participant_count',
            'is_joined',
            'is_active',
        ]

    def get_participant_count(self, obj):
        return obj.participants.filter(is_active=True).count()

    def get_is_joined(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.participants.filter(user=request.user, left_at__isnull=True).exists()
        return False

    def get_is_active(self, obj):
        return bool(getattr(obj, "is_active", False))


class StudyRoomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating StudyRoom"""

    class Meta:
        model = StudyRoom
        fields = [
            'name',
            'description',
            'room_type',
            'study_group',
            'max_participants',
            'is_recording_enabled',
            'is_screen_share_enabled',
        ]

    def create(self, validated_data):
        validated_data['host'] = self.context['request'].user
        validated_data['started_at'] = timezone.now()
        validated_data['status'] = StudyRoom.RoomStatus.ACTIVE
        return super().create(validated_data)


class RoomParticipantSerializer(serializers.ModelSerializer):
    """Serializer for RoomParticipant model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.URLField(source='user.avatar_url', read_only=True)
    is_host = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = RoomParticipant
        fields = [
            'id', 'user', 'user_name', 'user_avatar', 'room',
            'role', 'status', 'peer_id', 'is_audio_enabled', 'is_video_enabled',
            'is_screen_sharing', 'joined_at', 'left_at', 'is_active', 'is_host',
        ]
        read_only_fields = ['id', 'joined_at', 'is_host']

    def get_is_host(self, obj):
        return obj.room.host == obj.user

    def get_is_active(self, obj):
        return bool(getattr(obj, "is_active", False))


class RoomMessageSerializer(serializers.ModelSerializer):
    """Serializer for RoomMessage model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.URLField(source='user.avatar_url', read_only=True)
    content = serializers.CharField(source='message', required=False)

    class Meta:
        model = RoomMessage
        fields = [
            'id', 'room', 'user', 'user_name', 'user_avatar',
            'message', 'content', 'message_type', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class RoomRecordingSerializer(serializers.ModelSerializer):
    """Serializer for RoomRecording model"""

    class Meta:
        model = RoomRecording
        fields = [
            'id',
            'room',
            'recorded_by',
            'duration',
            'file_size',
            'file_url',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
