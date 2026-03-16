"""App configuration for search."""

from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.search"
    verbose_name = "Search"

    def ready(self):
        import apps.search.signals  # noqa: F401
