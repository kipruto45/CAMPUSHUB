"""
App configuration for Live Study Rooms
"""

from django.apps import AppConfig


class LiveRoomsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.live_rooms'
    verbose_name = 'Live Study Rooms'

    def ready(self):
        # Import signals when app is ready
        try:
            import apps.live_rooms.signals  # noqa
        except ImportError:
            pass
