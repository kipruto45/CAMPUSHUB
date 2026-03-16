"""
App configuration for activity app.
"""

from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.activity"
    verbose_name = "Activity Tracking"

    def ready(self):
        # Import signals when app is ready
        try:
            import apps.activity.signals  # noqa: F401
        except ImportError:
            pass
