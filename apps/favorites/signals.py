"""Signal handlers for favorites automations."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Favorite, FavoriteType


@receiver(post_save, sender=Favorite)
def sync_is_favorite_to_model(sender, instance, created, **kwargs):
    """Sync denormalized `is_favorite` flags on personal models."""
    if (
        instance.favorite_type == FavoriteType.PERSONAL_FILE
        and instance.personal_file_id
    ):
        if not instance.personal_file.is_favorite:
            instance.personal_file.is_favorite = True
            instance.personal_file.save(update_fields=["is_favorite"])
    elif instance.favorite_type == FavoriteType.FOLDER and instance.personal_folder_id:
        if not instance.personal_folder.is_favorite:
            instance.personal_folder.is_favorite = True
            instance.personal_folder.save(update_fields=["is_favorite"])


@receiver(post_save, sender=Favorite)
def notify_resource_like(sender, instance, created, **kwargs):
    """Notify resource owners when their resources are liked."""
    if not created:
        return
    if instance.favorite_type != FavoriteType.RESOURCE or not instance.resource_id:
        return

    try:
        from apps.notifications.services import NotificationService

        NotificationService.notify_resource_liked(instance)
    except Exception:
        return


@receiver(post_delete, sender=Favorite)
def sync_is_unfavorite_from_model(sender, instance, **kwargs):
    """Unset denormalized `is_favorite` flags when favorite rows are removed."""
    if (
        instance.favorite_type == FavoriteType.PERSONAL_FILE
        and instance.personal_file_id
    ):
        still_favorited = Favorite.objects.filter(
            user=instance.user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file_id=instance.personal_file_id,
        ).exists()
        if not still_favorited and instance.personal_file.is_favorite:
            instance.personal_file.is_favorite = False
            instance.personal_file.save(update_fields=["is_favorite"])
    elif instance.favorite_type == FavoriteType.FOLDER and instance.personal_folder_id:
        still_favorited = Favorite.objects.filter(
            user=instance.user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder_id=instance.personal_folder_id,
        ).exists()
        if not still_favorited and instance.personal_folder.is_favorite:
            instance.personal_folder.is_favorite = False
            instance.personal_folder.save(update_fields=["is_favorite"])
