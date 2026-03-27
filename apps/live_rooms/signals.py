"""
Signals for Live Study Rooms
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import StudyRoom, RoomParticipant, RoomRecording


@receiver(post_save, sender=RoomParticipant)
def update_room_participant_count(sender, instance, created, **kwargs):
    """Best-effort hook for participant updates."""
    # StudyRoom does not persist current_participants, so no write needed.
    return


@receiver(pre_delete, sender=RoomParticipant)
def update_room_participant_count_on_delete(sender, instance, **kwargs):
    """Best-effort hook for participant deletes."""
    # StudyRoom does not persist current_participants, so no write needed.
    return


@receiver(post_save, sender=StudyRoom)
def on_room_created(sender, instance, created, **kwargs):
    """When a room is created, add the host as a participant"""
    if created:
        RoomParticipant.objects.get_or_create(
            room=instance,
            user=instance.host,
            defaults={
                'joined_at': timezone.now(),
                'status': RoomParticipant.Status.CONNECTED,
                'role': RoomParticipant.Role.HOST,
                'left_at': None,
            }
        )
