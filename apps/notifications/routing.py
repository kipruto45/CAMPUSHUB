"""
WebSocket URL routing for notifications.
"""

from django.urls import re_path

from apps.notifications.consumers import (ActivityConsumer,
                                          GlobalNotificationConsumer,
                                          NotificationConsumer)

websocket_urlpatterns = [
    # User notifications - ws://host/ws/notifications/
    re_path(
        r"^ws/notifications/$", NotificationConsumer.as_asgi(), name="ws_notifications"
    ),
    # Global admin notifications - ws://host/ws/admin/notifications/
    re_path(
        r"^ws/admin/notifications/$",
        GlobalNotificationConsumer.as_asgi(),
        name="ws_admin_notifications",
    ),
    # Activity stream for admins - ws://host/ws/activity/
    re_path(r"^ws/activity/$", ActivityConsumer.as_asgi(), name="ws_activity"),
]
