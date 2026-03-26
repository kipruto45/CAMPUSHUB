"""
Notes Serializers for CampusHub
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from .models import Note, NoteShare, NoteVersion, NotePresence, NoteLock

User = get_user_model()


@extend_schema_serializer(component_name="NoteUser")
class UserSerializer(serializers.ModelSerializer):
    """Serializer for user info"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id', 'username']


class NoteShareSerializer(serializers.ModelSerializer):
    """Serializer for note sharing"""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = NoteShare
        fields = [
            'id', 'user', 'user_id', 'permission', 'is_active',
            'can_share', 'can_copy', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NoteVersionSerializer(serializers.ModelSerializer):
    """Serializer for note version history"""
    
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = NoteVersion
        fields = [
            'id', 'version_number', 'title', 'content', 'content_html',
            'change_summary', 'created_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotePresenceSerializer(serializers.ModelSerializer):
    """Serializer for note presence"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = NotePresence
        fields = [
            'id', 'user', 'activity', 'cursor_position', 'cursor_selection',
            'last_active', 'is_online'
        ]
        read_only_fields = ['id', 'last_active']


class NoteLockSerializer(serializers.ModelSerializer):
    """Serializer for note lock"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = NoteLock
        fields = ['id', 'user', 'lock_type', 'expires_at', 'created_at']
        read_only_fields = ['id', 'created_at']


class NoteListSerializer(serializers.ModelSerializer):
    """Serializer for note list view"""
    
    owner = UserSerializer(read_only=True)
    share_count = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'status', 'folder', 'tags', 'is_collaborative',
            'owner', 'share_count', 'version_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.IntegerField())
    def get_share_count(self, obj) -> int:
        return obj.shares.filter(is_active=True).count()
    
    @extend_schema_field(serializers.IntegerField())
    def get_version_count(self, obj) -> int:
        return obj.versions.count()


class NoteDetailSerializer(serializers.ModelSerializer):
    """Serializer for note detail view"""
    
    owner = UserSerializer(read_only=True)
    shares = NoteShareSerializer(many=True, read_only=True)
    versions = NoteVersionSerializer(many=True, read_only=True)
    presence = serializers.SerializerMethodField()
    active_lock = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'content_html', 'status', 'folder',
            'tags', 'is_collaborative', 'lock_timeout',
            'owner', 'shares', 'versions', 'presence', 'active_lock',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']
    
    @extend_schema_field(NotePresenceSerializer(many=True))
    def get_presence(self, obj):
        """Get active presence for the note"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get users active in the last 5 minutes
        threshold = timezone.now() - timedelta(minutes=5)
        presence = obj.presence.filter(
            is_online=True,
            last_active__gte=threshold
        ).select_related('user')
        return NotePresenceSerializer(presence, many=True).data
    
    @extend_schema_field(NoteLockSerializer(allow_null=True))
    def get_active_lock(self, obj):
        """Get active lock for the note"""
        from django.utils import timezone
        
        lock = obj.locks.filter(expires_at__gt=timezone.now()).first()
        if lock:
            return NoteLockSerializer(lock).data
        return None


class NoteCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notes"""
    
    class Meta:
        model = Note
        fields = [
            'title', 'content', 'content_html', 'status', 'folder',
            'tags', 'is_collaborative', 'lock_timeout'
        ]
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class NoteUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating notes"""
    
    class Meta:
        model = Note
        fields = [
            'title', 'content', 'content_html', 'status', 'folder',
            'tags', 'is_collaborative', 'lock_timeout'
        ]


class NoteShareCreateSerializer(serializers.Serializer):
    """Serializer for creating note shares"""
    
    user_id = serializers.UUIDField()
    permission = serializers.ChoiceField(choices=NoteShare.Permission.choices, default=NoteShare.Permission.VIEW)
    can_share = serializers.BooleanField(default=False)
    can_copy = serializers.BooleanField(default=True)


class NoteVersionCreateSerializer(serializers.Serializer):
    """Serializer for creating note versions"""
    
    change_summary = serializers.CharField(max_length=500, required=False, allow_blank=True)
