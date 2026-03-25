"""
WebSocket consumers for real-time notifications.
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Connects to user-specific notification groups.
    """

    async def _send_json(self, payload: dict) -> None:
        """Send JSON payloads safely (UUID/datetime friendly)."""
        await self.send(text_data=json.dumps(payload, default=str))

    async def connect(self):
        self.user = self.scope.get("user")
        self.joined_user_group = False

        # Only authenticated users can connect
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.user_group = f"notifications_{self.user.id}"
        await self.accept()

        # Join group first so immediate events after handshake are not lost.
        try:
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            self.joined_user_group = True
        except Exception:
            self.joined_user_group = False

        # Send connection confirmation once subscription is ready.
        await self._send_json(
            {
                "type": "connection",
                "message": "Connected to notification service",
                "user_id": self.user.id,
            }
        )

    async def disconnect(self, close_code):
        # Leave user notification group
        if getattr(self, "joined_user_group", False) and hasattr(self, "user_group"):
            try:
                await self.channel_layer.group_discard(
                    self.user_group, self.channel_name
                )
            except Exception:
                pass

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "pong",
                            "timestamp": data.get("timestamp"),
                        }
                    )
                )
            elif message_type == "mark_read":
                # Mark notification as read
                notification_id = data.get("notification_id")
                if notification_id:
                    updated = await self.mark_notification_read(notification_id)
                    if updated:
                        # Acknowledge immediately to the connected client.
                        await self._send_json(
                            {
                                "type": "notification_read",
                                "notification_id": notification_id,
                            }
                        )
                    else:
                        await self._send_json(
                            {
                                "type": "error",
                                "message": "Notification not found.",
                            }
                        )

        except json.JSONDecodeError:
            await self._send_json(
                {
                    "type": "error",
                    "message": "Invalid JSON",
                }
            )
        except Exception as e:
            await self._send_json(
                {
                    "type": "error",
                    "message": str(e),
                }
            )

    async def notification_message(self, event):
        """
        Handle notification messages from channel layer.
        This is called when a notification is sent to the user's group.
        """
        await self._send_json(
            {
                "type": "notification",
                "id": event.get("id"),
                "title": event.get("title"),
                "message": event.get("message"),
                "notification_type": event.get("notification_type"),
                "timestamp": event.get("timestamp"),
                "link": event.get("link"),
                "read": event.get("read", False),
            }
        )

    async def notification_read(self, event):
        """
        Handle notification read status update.
        """
        await self._send_json(
            {
                "type": "notification_read",
                "notification_id": event.get("notification_id"),
            }
        )

    async def notification_deleted(self, event):
        """
        Handle notification deletion.
        """
        await self._send_json(
            {
                "type": "notification_deleted",
                "notification_id": event.get("notification_id"),
            }
        )

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read."""
        from apps.notifications.models import Notification

        notification = Notification.objects.filter(
            id=notification_id,
            recipient_id=getattr(self.user, "id", None),
        ).first()
        if not notification:
            return False

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])

        return True


class GlobalNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for global/platform-wide notifications.
    Only accessible by admin users.
    """

    async def _send_json(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload, default=str))

    async def connect(self):
        self.user = self.scope.get("user")
        self.joined_global_group = False

        # Only authenticated admin users can connect
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        if not self.user.is_staff and not self.user.is_superuser:
            await self.close()
            return

        await self.accept()

        # Join group first so admin receives immediate broadcast events.
        try:
            await self.channel_layer.group_add(
                "global_notifications", self.channel_name
            )
            self.joined_global_group = True
        except Exception:
            self.joined_global_group = False

        await self._send_json(
            {
                "type": "connection",
                "message": "Connected to global notification service",
                "user_id": self.user.id,
            }
        )

    async def disconnect(self, close_code):
        if self.joined_global_group:
            try:
                await self.channel_layer.group_discard(
                    "global_notifications", self.channel_name
                )
            except Exception:
                pass

    async def receive(self, text_data):
        """Handle incoming WebSocket messages for admin."""
        try:
            json.loads(text_data)
            # Admin-specific message handling
        except Exception:
            pass

    async def global_notification(self, event):
        """Handle global notifications."""
        await self._send_json(
            {
                "type": "global_notification",
                "title": event.get("title"),
                "message": event.get("message"),
                "priority": event.get("priority"),
                "timestamp": event.get("timestamp"),
            }
        )


class ActivityConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time activity updates.
    Shows recent activities across the platform (for admins).
    """

    async def connect(self):
        self.user = self.scope.get("user")
        self.joined_activity_group = False

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        if not self.user.is_staff and not self.user.is_superuser:
            await self.close()
            return

        await self.accept()

        # Join activity stream group before returning from connect.
        try:
            await self.channel_layer.group_add("activity_stream", self.channel_name)
            self.joined_activity_group = True
        except Exception:
            self.joined_activity_group = False

    async def disconnect(self, close_code):
        if self.joined_activity_group:
            try:
                await self.channel_layer.group_discard(
                    "activity_stream", self.channel_name
                )
            except Exception:
                pass

    async def activity_update(self, event):
        """Handle activity updates."""
        await self._send_json(
            {
                "type": "activity",
                "activity_type": event.get("activity_type"),
                "user": event.get("user"),
                "resource": event.get("resource"),
                "timestamp": event.get("timestamp"),
            }
        )

    async def _send_json(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload, default=str))
