"""
Signals for Live Study Rooms
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import StudyRoom, RoomParticipant, RoomRecording


@receiver(post_save, sender=RoomParticipant)
def update_room_participant_count(sender, instance, created, **kwargs):
    """Update room participant count when a participant joins or leaves"""
    room = instance.room
    room.current_participants = room.participants.filter(is_active=True).count()
    room.save(update_fields=['current_participants'])


@receiver(pre_delete, sender=RoomParticipant)
def update_room_participant_count_on_delete(sender, instance, **kwargs):
    """Update room participant count when a participant is deleted"""
    room = instance.room
    room.current_participants = room.participants.filter(is_active=True).exclude(pk=instance.pk).count()
    room.save(update_fields=['current_participants'])


@receiver(post_save, sender=StudyRoom)
def on_room_created(sender, instance, created, **kwargs):
    """When a room is created, add the host as a participant"""
    if created:
        RoomParticipant.objects.get_or_create(
            room=instance,
            user=instance.host,
            defaults={
                'joined_at': timezone.now(),
                'is_active': True,
            }
        )
        instance.current_participants = 1
        instance.save(update_fields=['current_participants'])
