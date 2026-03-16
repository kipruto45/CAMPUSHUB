"""Signals for keeping search index in sync with resources."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.resources.models import Resource
from apps.search.models import SearchIndex
from apps.search.services import SearchService


@receiver(post_save, sender=Resource)
def upsert_search_index(sender, instance, **kwargs):
    """Index approved public resources and remove hidden ones."""
    if instance.status == "approved" and instance.is_public:
        document = SearchService.build_search_document(instance)
        SearchIndex.objects.update_or_create(
            resource=instance,
            defaults={
                "search_document": document,
                "is_active": True,
            },
        )
    else:
        SearchIndex.objects.filter(resource=instance).delete()


@receiver(post_delete, sender=Resource)
def delete_search_index(sender, instance, **kwargs):
    """Drop index rows for deleted resources."""
    SearchIndex.objects.filter(resource=instance).delete()
