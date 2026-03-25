"""
Calendar app configuration.
"""

from django.apps import AppConfig


class CalendarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.calendar"
    verbose_name = "Calendar & Timetable"

    def ready(self):
        """Initialize calendar app."""
        import apps.calendar.signals  # noqa: F401