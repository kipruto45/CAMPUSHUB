"""
Notes Views for CampusHub
REST API endpoints for note operations
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from .models import Note, NoteShare, NoteVersion, NotePresence, NoteLock
from .serializers import (
    NoteListSerializer, NoteDetailSerializer, NoteCreateSerializer, NoteUpdateSerializer,
    NoteShareSerializer, NoteShareCreateSerializer,
    NoteVersionSerializer, NoteVersionCreateSerializer,
    NotePresenceSerializer, NoteLockSerializer
)
from .services import NoteService, CollaborationService, ShareService

User = get_user_model()


class NoteViewSet(viewsets.ModelViewSet):
    """ViewSet for note CRUD operations"""
    
    permission_classes = [IsAuthenticated]
    queryset = Note.objects.none()
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Note.objects.none()
        return NoteService.get_note_queryset(self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NoteListSerializer
        elif self.action == 'create':
            return NoteCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return NoteUpdateSerializer
        return NoteDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        note = self.get_object()
        # Only owner can delete
        if note.owner != request.user:
            return Response(
                {'error': 'Only the owner can delete this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share a note with another user"""
        note = self.get_object()
        
        # Check permission
        if note.owner != request.user:
            share = note.shares.filter(user=request.user, is_active=True).first()
            if not share or share.permission != NoteShare.Permission.ADMIN:
                return Response(
                    {'error': 'You do not have permission to share this note'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = NoteShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get target user
        try:
            target_user = User.objects.get(id=serializer.validated_data['user_id'])
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Share the note
        share = ShareService.share_note(
            note=note,
            user=request.user,
            target_user=target_user,
            permission=serializer.validated_data.get('permission', NoteShare.Permission.VIEW),
            can_share=serializer.validated_data.get('can_share', False),
            can_copy=serializer.validated_data.get('can_copy', True)
        )
        
        return Response(
            NoteShareSerializer(share).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description="User ID whose note share should be revoked.",
            )
        ]
    )
    @action(
        detail=True,
        methods=['delete'],
        url_path='share/(?P<user_id>[0-9a-fA-F-]{36})',
    )
    def revoke_share(self, request, pk=None, user_id=None):
        """Revoke a user's access to a note"""
        note = self.get_object()
        
        # Check permission
        if note.owner != request.user:
            share = note.shares.filter(user=request.user, is_active=True).first()
            if not share or share.permission != NoteShare.Permission.ADMIN:
                return Response(
                    {'error': 'You do not have permission to revoke shares'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        ShareService.revoke_share(note, target_user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        """Get version history for a note"""
        note = self.get_object()
        
        if not NoteService.can_view_note(request.user, note):
            return Response(
                {'error': 'You do not have permission to view this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        versions = note.versions.all()[:50]  # Limit to 50 versions
        serializer = NoteVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='versions')
    def create_version(self, request, pk=None):
        """Create a new version of the note"""
        note = self.get_object()
        
        if not NoteService.can_edit_note(request.user, note):
            return Response(
                {'error': 'You do not have permission to edit this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = NoteVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        version = NoteService.create_version(
            note=note,
            user=request.user,
            change_summary=serializer.validated_data.get('change_summary', '')
        )
        
        return Response(
            NoteVersionSerializer(version).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="version_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description="Version ID to restore.",
            )
        ]
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='versions/(?P<version_id>[0-9a-fA-F-]{36})/restore',
    )
    def restore_version(self, request, pk=None, version_id=None):
        """Restore a note to a previous version"""
        note = self.get_object()
        
        if not NoteService.can_edit_note(request.user, note):
            return Response(
                {'error': 'You do not have permission to edit this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            version = NoteVersion.objects.get(id=version_id, note=note)
        except NoteVersion.DoesNotExist:
            return Response(
                {'error': 'Version not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Restore content
        note.title = version.title
        note.content = version.content
        note.content_html = version.content_html
        note.save()
        
        # Create a new version for the restore
        NoteService.create_version(
            note=note,
            user=request.user,
            change_summary=f"Restored to version {version.version_number}"
        )
        
        return Response(NoteDetailSerializer(note).data)
    
    @action(detail=True, methods=['get'], url_path='presence')
    def presence(self, request, pk=None):
        """Get active users on a note"""
        note = self.get_object()
        
        if not NoteService.can_view_note(request.user, note):
            return Response(
                {'error': 'You do not have permission to view this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        active_users = CollaborationService.get_active_users(note)
        serializer = NotePresenceSerializer(active_users, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='lock')
    def acquire_lock(self, request, pk=None):
        """Acquire a lock on a note for editing"""
        note = self.get_object()
        
        if not NoteService.can_edit_note(request.user, note):
            return Response(
                {'error': 'You do not have permission to edit this note'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        lock, created = CollaborationService.acquire_lock(note, request.user)
        
        if not lock:
            return Response(
                {'error': 'Note is locked by another user'},
                status=status.HTTP_409_CONFLICT
            )
        
        return Response(NoteLockSerializer(lock).data)
    
    @action(detail=True, methods=['delete'], url_path='lock')
    def release_lock(self, request, pk=None):
        """Release a lock on a note"""
        note = self.get_object()
        CollaborationService.release_lock(note, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='lock')
    def check_lock(self, request, pk=None):
        """Check if note is locked"""
        note = self.get_object()
        lock = CollaborationService.check_lock(note)
        
        if lock:
            return Response(NoteLockSerializer(lock).data)
        return Response({'locked': False})


class NoteListView(generics.ListAPIView):
    """List all notes accessible to the user"""
    
    serializer_class = NoteListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Note.objects.none()
        return NoteService.get_note_queryset(self.request.user).filter(
            status=Note.NoteStatus.PUBLISHED
        )


class NoteCreateView(generics.CreateAPIView):
    """Create a new note"""
    
    serializer_class = NoteCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a note"""
    
    serializer_class = NoteDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Note.objects.none()
        return NoteService.get_note_queryset(self.request.user)
    
    def perform_update(self, serializer):
        note = self.get_object()
        if not NoteService.can_edit_note(self.request.user, note):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to edit this note")
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the owner can delete this note")
        instance.delete()
