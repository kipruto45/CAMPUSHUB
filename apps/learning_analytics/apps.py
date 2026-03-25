"""
App configuration for Learning Analytics
"""

from django.apps import AppConfig


class LearningAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.learning_analytics'
    verbose_name = 'Learning Analytics'

    def ready(self):
        pass  # Signals can be added here later
