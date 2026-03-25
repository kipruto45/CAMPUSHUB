from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """Configuration for the Integrations app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations'
    label = 'integrations'
    verbose_name = 'Integrations'