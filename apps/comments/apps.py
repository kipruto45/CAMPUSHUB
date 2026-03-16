"""App configuration for comments."""

from django.apps import AppConfig


class CommentsConfig(AppConfig):
    """Comments app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comments"
    verbose_name = "Comments"

    def ready(self):
        """Register signal handlers."""
        import apps.comments.signals  # noqa: F401
