"""
Gamification app configuration.
"""

from django.apps import AppConfig


class GamificationConfig(AppConfig):
    """Configuration for the gamification app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.gamification"
    verbose_name = "Gamification"
