"""
App configuration for favorites app.
"""

from django.apps import AppConfig


class FavoritesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.favorites"
    verbose_name = "Favorites"

    def ready(self):
        try:
            import apps.favorites.signals  # noqa: F401
        except ImportError:
            pass
