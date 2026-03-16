"""Downloads app configuration."""

from django.apps import AppConfig


class DownloadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.downloads"
    verbose_name = "Downloads"

    def ready(self):
        import apps.downloads.tasks  # noqa: F401
