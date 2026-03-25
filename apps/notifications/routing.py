"""
WebSocket URL routing for notifications and chat.
"""

from django.urls import re_path

from apps.notes.consumers import NoteConsumer
from apps.notifications.consumers import (ActivityConsumer,
                                          GlobalNotificationConsumer,
                                          NotificationConsumer)
from apps.social.consumers import (ChatConsumer, GroupChatConsumer,
                                   OnlineStatusConsumer)

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
    # Direct messaging - ws://host/ws/chat/
    re_path(r"^ws/chat/$", ChatConsumer.as_asgi(), name="ws_chat"),
    # Group/study group chat - ws://host/ws/groups/
    re_path(r"^ws/groups/$", GroupChatConsumer.as_asgi(), name="ws_groups"),
    # Online status tracking - ws://host/ws/status/
    re_path(r"^ws/status/$", OnlineStatusConsumer.as_asgi(), name="ws_status"),
    # Collaborative note editing - ws://host/ws/notes/
    re_path(r"^ws/notes/$", NoteConsumer.as_asgi(), name="ws_notes"),
]
