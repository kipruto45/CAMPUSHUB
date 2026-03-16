"""
Real-time WebSocket consumers for typing indicators and online presence.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class TypingIndicatorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time typing indicators.
    Allows users to see when others are typing.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.rooms = set()  # Track active rooms/channels
        await self.accept()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "message": "Connected to typing indicator service",
                }
            )
        )

    async def disconnect(self, close_code):
        # Leave all typing rooms
        for room in self.rooms:
            try:
                await self.channel_layer.group_discard(
                    f"typing_{room}", self.channel_name
                )
            except Exception as exc:
                logger.debug("Failed to leave typing room '%s': %s", room, exc)

        # Broadcast user went offline
        await self.update_online_status(False)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "typing_start":
                room = data.get("room")
                room_type = data.get("room_type", "resource")
                if room:
                    await self.start_typing(room, room_type)

            elif message_type == "typing_stop":
                room = data.get("room")
                room_type = data.get("room_type", "resource")
                if room:
                    await self.stop_typing(room, room_type)

            elif message_type == "join_room":
                room = data.get("room")
                room_type = data.get("room_type", "resource")
                if room:
                    await self.join_room(room, room_type)

            elif message_type == "leave_room":
                room = data.get("room")
                room_type = data.get("room_type", "resource")
                if room:
                    await self.leave_room(room, room_type)

            elif message_type == "heartbeat":
                await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))

        except Exception as exc:
            logger.warning("Typing consumer receive error: %s", exc)

    async def start_typing(self, room: str, room_type: str):
        """Broadcast typing started to room."""
        group = f"typing_{room}"
        user_info = {
            "user_id": self.user.id,
            "name": self.user.get_full_name() or self.user.email,
            "avatar": getattr(self.user, "profile_image", None),
        }

        await self.channel_layer.group_send(
            group,
            {
                "type": "typing_started",
                "room": room,
                "room_type": room_type,
                "user": user_info,
            },
        )

        await self.channel_layer.group_add(group, self.channel_name)
        self.rooms.add(room)

    async def stop_typing(self, room: str, room_type: str):
        """Broadcast typing stopped to room."""
        group = f"typing_{room}"
        user_info = {
            "user_id": self.user.id,
            "name": self.user.get_full_name() or self.user.email,
        }

        await self.channel_layer.group_send(
            group,
            {
                "type": "typing_stopped",
                "room": room,
                "room_type": room_type,
                "user": user_info,
            },
        )

    async def join_room(self, room: str, room_type: str):
        """Join a typing indicator room."""
        group = f"typing_{room}"
        await self.channel_layer.group_add(group, self.channel_name)
        self.rooms.add(room)

        await self.channel_layer.group_send(
            group,
            {
                "type": "user_joined",
                "room": room,
                "user": {
                    "user_id": self.user.id,
                    "name": self.user.get_full_name() or self.user.email,
                },
            },
        )

    async def leave_room(self, room: str, room_type: str):
        """Leave a typing indicator room."""
        group = f"typing_{room}"
        await self.channel_layer.group_discard(group, self.channel_name)
        self.rooms.discard(room)

        await self.channel_layer.group_send(
            group,
            {
                "type": "user_left",
                "room": room,
                "user": {
                    "user_id": self.user.id,
                    "name": self.user.get_full_name() or self.user.email,
                },
            },
        )

    async def typing_started(self, event):
        """Handle incoming typing started message."""
        if event.get("user", {}).get("user_id") != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing_started",
                        "room": event.get("room"),
                        "room_type": event.get("room_type"),
                        "user": event.get("user"),
                    }
                )
            )

    async def typing_stopped(self, event):
        """Handle incoming typing stopped message."""
        if event.get("user", {}).get("user_id") != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing_stopped",
                        "room": event.get("room"),
                        "room_type": event.get("room_type"),
                        "user": event.get("user"),
                    }
                )
            )

    async def user_joined(self, event):
        """Handle user joined room."""
        if event.get("user", {}).get("user_id") != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "user_joined",
                        "room": event.get("room"),
                        "user": event.get("user"),
                    }
                )
            )

    async def user_left(self, event):
        """Handle user left room."""
        if event.get("user", {}).get("user_id") != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "user_left",
                        "room": event.get("room"),
                        "user": event.get("user"),
                    }
                )
            )

    @database_sync_to_async
    def update_online_status(self, is_online: bool):
        """Update user online status in database."""
        if not getattr(self, "user", None) or not self.user.is_authenticated:
            return

        User.objects.filter(pk=self.user.id).update(last_activity=timezone.now())
        cache_key = f"online_user:{self.user.id}"
        if is_online:
            cache.set(cache_key, True, timeout=300)
        else:
            cache.delete(cache_key)


class OnlineStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for online presence tracking.
    Tracks which users are currently online.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"
        await self.accept()

        # Add to user's personal group
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Broadcast online status
        await self.channel_layer.group_add("online_users", self.channel_name)
        await self.broadcast_online_status(True)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "message": "Connected to presence service",
                }
            )
        )

        # Send list of currently online users
        await self.send_online_users()

    async def disconnect(self, close_code):
        await self.broadcast_online_status(False)

        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        try:
            await self.channel_layer.group_discard("online_users", self.channel_name)
        except Exception as exc:
            logger.debug("Failed to leave online_users group: %s", exc)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "get_online_users":
                await self.send_online_users()

            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

        except Exception as exc:
            logger.warning("Online status consumer receive error: %s", exc)

    async def broadcast_online_status(self, is_online: bool):
        """Broadcast user's online status to all online users."""
        await self.channel_layer.group_send(
            "online_users",
            {
                "type": "user_online_status",
                "user_id": self.user.id,
                "is_online": is_online,
                "timestamp": timezone.now().isoformat(),
            },
        )

    async def send_online_users(self):
        """Send list of online users."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "online_users_list",
                    "message": "Online users tracking (using in-memory channels)",
                }
            )
        )

    async def user_online_status(self, event):
        """Handle user online status change."""
        if event.get("user_id") != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "user_online_status",
                        "user_id": event.get("user_id"),
                        "is_online": event.get("is_online"),
                        "timestamp": event.get("timestamp"),
                    }
                )
            )
