"""
Notes WebSocket Routing
"""

from django.urls import re_path

from .consumers import NoteConsumer

websocket_urlpatterns = [
    # Real-time collaborative editing - ws://host/ws/notes/
    re_path(r"^ws/notes/$", NoteConsumer.as_asgi(), name="ws_notes"),
]