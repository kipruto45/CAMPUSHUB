"""
App configuration for Calendar Sync
"""

from django.apps import AppConfig


class CalendarSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.calendar_sync'
    verbose_name = 'Calendar Sync'
