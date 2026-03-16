"""Signals for recommendation cache/profile automations."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.activity.models import ActivityType, RecentActivity
from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.ratings.models import Rating
from apps.recommendations.services import (
    invalidate_resource_recommendation_cache,
    invalidate_user_recommendation_cache, refresh_user_interest_profile)
from apps.resources.models import Resource


def _refresh_user(user):
    if not user or not getattr(user, "is_authenticated", True):
        return
    refresh_user_interest_profile(user)
    invalidate_user_recommendation_cache(user)


@receiver(post_save, sender=Download)
def download_saved(sender, instance, created, **kwargs):
    if created:
        _refresh_user(instance.user)


@receiver(post_delete, sender=Download)
def download_deleted(sender, instance, **kwargs):
    _refresh_user(instance.user)


@receiver(post_save, sender=Bookmark)
def bookmark_saved(sender, instance, created, **kwargs):
    if created:
        _refresh_user(instance.user)


@receiver(post_delete, sender=Bookmark)
def bookmark_deleted(sender, instance, **kwargs):
    _refresh_user(instance.user)


@receiver(post_save, sender=Rating)
def rating_saved(sender, instance, **kwargs):
    _refresh_user(instance.user)


@receiver(post_delete, sender=Rating)
def rating_deleted(sender, instance, **kwargs):
    _refresh_user(instance.user)


@receiver(post_save, sender=Favorite)
def favorite_saved(sender, instance, created, **kwargs):
    if created and instance.favorite_type == FavoriteType.RESOURCE:
        _refresh_user(instance.user)


@receiver(post_delete, sender=Favorite)
def favorite_deleted(sender, instance, **kwargs):
    if instance.favorite_type == FavoriteType.RESOURCE:
        _refresh_user(instance.user)


@receiver(post_save, sender=RecentActivity)
def activity_saved(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.activity_type in {
        ActivityType.VIEWED_RESOURCE,
        ActivityType.DOWNLOADED_RESOURCE,
        ActivityType.BOOKMARKED_RESOURCE,
        ActivityType.RATED,
    }:
        _refresh_user(instance.user)


@receiver(post_save, sender=Resource)
def resource_saved(sender, instance, **kwargs):
    invalidate_resource_recommendation_cache(instance)


@receiver(post_delete, sender=Resource)
def resource_deleted(sender, instance, **kwargs):
    invalidate_resource_recommendation_cache(instance)
