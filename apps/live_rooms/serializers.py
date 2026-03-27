"""
Serializers for Live Study Rooms
"""

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import StudyRoom, RoomParticipant, RoomMessage, RoomRecording


class StudyRoomSerializer(serializers.ModelSerializer):
    """Serializer for StudyRoom model"""
    host_name = serializers.SerializerMethodField()
    host_avatar = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    current_participants = serializers.SerializerMethodField()
    is_joined = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    is_recording = serializers.SerializerMethodField()
    privacy = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()
    end_time = serializers.DateTimeField(source="ended_at", read_only=True)

    class Meta:
        model = StudyRoom
        fields = [
            'id',
            'name',
            'description',
            'room_type',
            'privacy',
            'status',
            'host',
            'host_name',
            'host_avatar',
            'study_group',
            'max_participants',
            'is_recording_enabled',
            'is_screen_share_enabled',
            'started_at',
            'ended_at',
            'end_time',
            'created_at',
            'updated_at',
            'participant_count',
            'current_participants',
            'is_joined',
            'is_active',
            'is_recording',
            'share_url',
        ]
        read_only_fields = [
            'id',
            'host',
            'created_at',
            'updated_at',
            'participant_count',
            'current_participants',
            'is_joined',
            'is_active',
            'is_recording',
            'share_url',
        ]

    @extend_schema_field(serializers.CharField())
    def get_host_name(self, obj) -> str:
        full_name = obj.host.get_full_name()
        if full_name:
            return full_name
        return getattr(obj.host, "email", "") or getattr(obj.host, "username", "") or "Host"

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_host_avatar(self, obj) -> str | None:
        profile_image = getattr(obj.host, "profile_image", None)
        if not profile_image:
            return None
        try:
            url = profile_image.url
        except Exception:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    @extend_schema_field(serializers.IntegerField())
    def get_participant_count(self, obj) -> int:
        return obj.participants.filter(
            left_at__isnull=True,
            status=RoomParticipant.Status.CONNECTED,
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_current_participants(self, obj) -> int:
        return self.get_participant_count(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_is_joined(self, obj) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.participants.filter(user=request.user, left_at__isnull=True).exists()
        return False

    @extend_schema_field(serializers.BooleanField())
    def get_is_active(self, obj) -> bool:
        return bool(getattr(obj, "is_active", False))

    @extend_schema_field(serializers.BooleanField())
    def get_is_recording(self, obj) -> bool:
        return obj.recordings.filter(status=RoomRecording.Status.RECORDING).exists()

    @extend_schema_field(serializers.CharField())
    def get_privacy(self, obj) -> str:
        if obj.room_type == StudyRoom.RoomType.PRIVATE:
            return "private"
        if obj.room_type == StudyRoom.RoomType.STUDY_GROUP:
            return "invite_only"
        return "public"

    @extend_schema_field(serializers.URLField())
    def get_share_url(self, obj) -> str:
        request = self.context.get("request")
        frontend_base = str(
            getattr(settings, "FRONTEND_BASE_URL", "")
            or getattr(settings, "FRONTEND_URL", "")
            or getattr(settings, "RESOURCE_SHARE_BASE_URL", "")
            or getattr(settings, "WEB_APP_URL", "")
            or ""
        ).rstrip("/")
        if frontend_base:
            return f"{frontend_base}/live-room/{obj.id}"

        try:
            from apps.accounts.views import _build_mobile_deeplink

            deeplink = _build_mobile_deeplink(f"live-room/{obj.id}")
            if deeplink:
                return deeplink
        except Exception:
            pass

        if request is not None:
            return request.build_absolute_uri(f"/live-room/{obj.id}")
        return f"/live-room/{obj.id}"


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
        room = super().create(validated_data)
        RoomParticipant.objects.update_or_create(
            room=room,
            user=room.host,
            defaults={
                "role": RoomParticipant.Role.HOST,
                "status": RoomParticipant.Status.CONNECTED,
                "left_at": None,
            },
        )
        return room


class RoomParticipantSerializer(serializers.ModelSerializer):
    """Serializer for RoomParticipant model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
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

    @extend_schema_field(serializers.BooleanField())
    def get_is_host(self, obj) -> bool:
        return obj.room.host == obj.user

    @extend_schema_field(serializers.BooleanField())
    def get_is_active(self, obj) -> bool:
        return bool(getattr(obj, "is_active", False))

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_user_avatar(self, obj) -> str | None:
        profile_image = getattr(obj.user, "profile_image", None)
        if not profile_image:
            return None
        try:
            url = profile_image.url
        except Exception:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class RoomMessageSerializer(serializers.ModelSerializer):
    """Serializer for RoomMessage model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    content = serializers.CharField(source='message', required=False)

    class Meta:
        model = RoomMessage
        fields = [
            'id', 'room', 'user', 'user_name', 'user_avatar',
            'message', 'content', 'message_type', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_user_avatar(self, obj) -> str | None:
        profile_image = getattr(obj.user, "profile_image", None)
        if not profile_image:
            return None
        try:
            url = profile_image.url
        except Exception:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url


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
