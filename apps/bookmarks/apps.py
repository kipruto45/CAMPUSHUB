"""App configuration for bookmarks."""

from django.apps import AppConfig


class BookmarksConfig(AppConfig):
    """Bookmarks app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bookmarks"
    verbose_name = "Bookmarks"

    def ready(self):
        """Register bookmark signals."""
        import apps.bookmarks.signals  # noqa: F401
