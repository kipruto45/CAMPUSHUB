"""App configuration for resources."""

from django.apps import AppConfig


class ResourcesConfig(AppConfig):
    """Resources app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.resources"
    verbose_name = "Resources"

    def ready(self):
        """Register signal handlers."""
        import apps.resources.signals  # noqa: F401
