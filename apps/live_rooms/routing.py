"""
WebSocket routing for Live Study Rooms
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/rooms/(?P<room_id>[^/]+)/$', consumers.StudyRoomConsumer.as_asgi()),
]
