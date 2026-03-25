from django.apps import AppConfig


class GoogleClassroomConfig(AppConfig):
    """Configuration for the Google Classroom integration app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations.google_classroom'
    label = 'google_classroom'
    verbose_name = 'Google Classroom Integration'