"""
Notes Signals for CampusHub
Automatic version creation and presence cleanup
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Note, NotePresence, NoteLock


@receiver(post_save, sender=Note)
def create_version_on_note_save(sender, instance, created, **kwargs):
    """Create a version when note is updated (if content changed significantly)"""
    # We handle version creation in the service layer to avoid unnecessary versions
    # This is a placeholder for any additional logic
    pass


@receiver(pre_delete, sender=Note)
def cleanup_on_note_delete(sender, instance, **kwargs):
    """Clean up related data when note is deleted"""
    # Delete related shares
    instance.shares.all().delete()
    
    # Delete related versions
    instance.versions.all().delete()
    
    # Delete presence records
    instance.presence.all().delete()
    
    # Delete locks
    instance.locks.all().delete()