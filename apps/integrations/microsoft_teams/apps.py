from django.apps import AppConfig


class MicrosoftTeamsConfig(AppConfig):
    """Configuration for the Microsoft Teams integration app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations.microsoft_teams'
    label = 'microsoft_teams'
    verbose_name = 'Microsoft Teams Integration'