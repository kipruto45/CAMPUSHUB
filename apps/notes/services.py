"""
Notes Services for CampusHub
Business logic for collaborative note editing
"""

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from .models import Note, NoteShare, NoteVersion, NotePresence, NoteLock

User = get_user_model()


class NoteService:
    """Service for note operations"""
    
    @staticmethod
    def get_note_queryset(user):
        """Get notes accessible to a user"""
        # Get notes owned by user
        owned = Note.objects.filter(owner=user)
        
        # Get notes shared with user
        shared = Note.objects.filter(
            shares__user=user,
            shares__is_active=True
        )
        
        # Combine and deduplicate
        return (owned | shared).distinct().select_related('owner')
    
    @staticmethod
    def can_edit_note(user, note):
        """Check if user can edit a note"""
        if note.owner == user:
            return True
        
        share = note.shares.filter(user=user, is_active=True).first()
        if share and share.permission in [NoteShare.Permission.EDIT, NoteShare.Permission.ADMIN]:
            return True
        
        return False
    
    @staticmethod
    def can_view_note(user, note):
        """Check if user can view a note"""
        if note.owner == user:
            return True
        
        share = note.shares.filter(user=user, is_active=True).first()
        return share is not None
    
    @staticmethod
    @transaction.atomic
    def create_version(note, user, change_summary=''):
        """Create a new version of the note"""
        # Get the next version number
        latest_version = note.versions.first()
        version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create version
        version = NoteVersion.objects.create(
            note=note,
            title=note.title,
            content=note.content,
            content_html=note.content_html,
            version_number=version_number,
            change_summary=change_summary,
            created_by=user
        )
        
        return version
    
    @staticmethod
    @transaction.atomic
    def update_note(note, user, data, create_version=True):
        """Update a note and optionally create a version"""
        old_content = note.content
        
        # Update note fields
        for field in ['title', 'content', 'content_html', 'status', 'folder', 'tags', 'is_collaborative', 'lock_timeout']:
            if field in data:
                setattr(note, field, data[field])
        
        note.save()
        
        # Create version if content changed significantly
        if create_version and note.content != old_content:
            NoteService.create_version(note, user, f"Updated note content")
        
        return note


class CollaborationService:
    """Service for real-time collaboration features"""
    
    @staticmethod
    def get_active_users(note):
        """Get users currently active on a note"""
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=5)
        
        return NotePresence.objects.filter(
            note=note,
            is_online=True,
            last_active__gte=threshold
        ).select_related('user')
    
    @staticmethod
    @transaction.atomic
    def update_presence(note, user, activity=None, cursor_position=None, cursor_selection=None):
        """Update user presence on a note"""
        presence, created = NotePresence.objects.get_or_create(
            note=note,
            user=user,
            defaults={
                'activity': activity or NotePresence.ActivityType.VIEWING,
                'cursor_position': cursor_position or 0,
                'cursor_selection': cursor_selection or {}
            }
        )
        
        if not created:
            if activity:
                presence.activity = activity
            if cursor_position is not None:
                presence.cursor_position = cursor_position
            if cursor_selection is not None:
                presence.cursor_selection = cursor_selection
            presence.is_online = True
            presence.save()
        
        return presence
    
    @staticmethod
    def set_offline(note, user):
        """Mark user as offline"""
        NotePresence.objects.filter(note=note, user=user).update(
            is_online=False,
            activity=NotePresence.ActivityType.IDLE
        )
    
    @staticmethod
    @transaction.atomic
    def acquire_lock(note, user, lock_type='edit'):
        """Acquire a lock on a note for editing"""
        # Check for existing valid lock
        existing_lock = note.locks.filter(
            expires_at__gt=timezone.now()
        ).first()
        
        if existing_lock and existing_lock.user != user:
            # Another user has the lock
            return None, False
        
        # Create or extend lock
        lock, created = NoteLock.objects.update_or_create(
            note=note,
            user=user,
            defaults={
                'lock_type': lock_type,
                'expires_at': timezone.now() + timedelta(seconds=note.lock_timeout)
            }
        )
        
        return lock, created
    
    @staticmethod
    def release_lock(note, user):
        """Release a lock on a note"""
        NoteLock.objects.filter(note=note, user=user).delete()
    
    @staticmethod
    def check_lock(note):
        """Check if note is locked"""
        lock = note.locks.filter(expires_at__gt=timezone.now()).first()
        return lock


class ShareService:
    """Service for note sharing"""
    
    @staticmethod
    @transaction.atomic
    def share_note(note, user, target_user, permission=NoteShare.Permission.VIEW, can_share=False, can_copy=True):
        """Share a note with another user"""
        share, created = NoteShare.objects.update_or_create(
            note=note,
            user=target_user,
            defaults={
                'permission': permission,
                'can_share': can_share,
                'can_copy': can_copy,
                'is_active': True
            }
        )
        return share
    
    @staticmethod
    @transaction.atomic
    def revoke_share(note, user):
        """Revoke a user's access to a note"""
        NoteShare.objects.filter(note=note, user=user).update(is_active=False)
    
    @staticmethod
    def get_shared_users(note):
        """Get all users a note is shared with"""
        return User.objects.filter(
            note_shares__note=note,
            note_shares__is_active=True
        ).select_related('note_shares')
