"""App configuration for ratings."""

from django.apps import AppConfig


class RatingsConfig(AppConfig):
    """Ratings app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ratings"
    verbose_name = "Ratings"

    def ready(self):
        """Register signal handlers."""
        import apps.ratings.signals  # noqa: F401
