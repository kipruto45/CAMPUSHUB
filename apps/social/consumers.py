"""
WebSocket consumers for real-time chat/messaging.
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time direct messaging.
    Handles one-on-one chat between users.
    """

    async def _send_json(self, payload: dict) -> None:
        """Send JSON payloads safely (UUID/datetime friendly)."""
        await self.send(text_data=json.dumps(payload, default=str))

    async def connect(self):
        self.user = self.scope.get("user")
        
        # Only authenticated users can connect
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = None
        await self.accept()

    async def disconnect(self, close_code):
        """Disconnect and leave chat room."""
        if hasattr(self, 'room_group_name') and self.room_group_name:
            try:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            except Exception:
                pass

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "typing":
                await self.handle_typing(data)
            elif message_type == "message":
                await self.handle_message(data)
            elif message_type == "read":
                await self.handle_read_receipt(data)
            elif message_type == "join":
                await self.handle_join(data)
            elif message_type == "leave":
                await self.handle_leave(data)

        except json.JSONDecodeError:
            await self._send_json({
                "type": "error",
                "message": "Invalid JSON"
            })
        except Exception as e:
            await self._send_json({
                "type": "error",
                "message": str(e)
            })

    async def handle_typing(self, data):
        """Handle typing indicator."""
        recipient_id = data.get("recipient_id")
        if not recipient_id:
            return

        # Create unique room for these two users
        user_ids = sorted([self.user.id, int(recipient_id)])
        room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"

        await self.channel_layer.group_send(
            room_group_name,
            {
                "type": "typing_indicator",
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": data.get("is_typing", True),
            }
        )

    async def handle_message(self, data):
        """Handle sending a message."""
        recipient_id = data.get("recipient_id")
        message_body = data.get("message", "").strip()

        if not recipient_id or not message_body:
            await self._send_json({
                "type": "error",
                "message": "recipient_id and message are required"
            })
            return

        # Save message to database
        message = await self.save_message(int(recipient_id), message_body)
        
        if message:
            # Create room group for both users
            user_ids = sorted([self.user.id, int(recipient_id)])
            room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"

            # Ensure both users are in the group
            await self.channel_layer.group_add(room_group_name, self.channel_name)

            # Send message to room group
            await self.channel_layer.group_send(
                room_group_name,
                {
                    "type": "chat_message",
                    "message_id": str(message.id),
                    "sender_id": self.user.id,
                    "sender_username": self.user.username,
                    "body": message_body,
                    "timestamp": message.created_at.isoformat(),
                }
            )
        else:
            await self._send_json({
                "type": "error",
                "message": "Failed to send message"
            })

    async def handle_read_receipt(self, data):
        """Handle read receipt."""
        message_id = data.get("message_id")
        if not message_id:
            return

        # Mark message as read
        updated = await self.mark_message_read(message_id)
        
        if updated:
            await self._send_json({
                "type": "read_receipt",
                "message_id": message_id,
                "read_at": updated.isoformat() if updated else None,
            })

    async def handle_join(self, data):
        """Handle joining a conversation."""
        # For direct messages, join the conversation room
        other_user_id = data.get("user_id")
        if not other_user_id:
            return

        user_ids = sorted([self.user.id, int(other_user_id)])
        self.room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self._send_json({
            "type": "joined",
            "room": self.room_group_name,
        })

    async def handle_leave(self, data):
        """Handle leaving a conversation."""
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Channel layer handlers
    async def chat_message(self, event):
        """Handle incoming chat message from group."""
        # Don't send back to sender (they already got acknowledgment)
        if event.get("sender_id") == self.user.id:
            return

        await self._send_json({
            "type": "message",
            "message_id": event.get("message_id"),
            "sender_id": event.get("sender_id"),
            "sender_username": event.get("sender_username"),
            "body": event.get("body"),
            "timestamp": event.get("timestamp"),
        })

    async def typing_indicator(self, event):
        """Handle typing indicator from group."""
        # Don't show typing indicator for own messages
        if event.get("user_id") == self.user.id:
            return

        await self._send_json({
            "type": "typing",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
            "is_typing": event.get("is_typing"),
        })

    @database_sync_to_async
    def save_message(self, recipient_id, body):
        """Save message to database."""
        from apps.social.models import Message

        try:
            recipient = User.objects.get(id=recipient_id)
            message = Message.objects.create(
                sender=self.user,
                recipient=recipient,
                body=body,
            )
            return message
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark message as read."""
        from apps.social.models import Message

        try:
            message = Message.objects.get(id=message_id, recipient=self.user)
            message.is_read = True
            message.read_at = timezone.now()
            message.save()
            return message
        except Message.DoesNotExist:
            return None


class GroupChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for group chat in study groups.
    """

    async def _send_json(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload, default=str))

    async def connect(self):
        self.user = self.scope.get("user")
        self.group_id = None
        self.room_group_name = None

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()

    async def disconnect(self, close_code):
        """Leave group chat room."""
        if self.room_group_name:
            try:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            except Exception:
                pass

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "typing":
                await self.handle_typing(data)
            elif message_type == "message":
                await self.handle_message(data)
            elif message_type == "join":
                await self.handle_join(data)

        except json.JSONDecodeError:
            await self._send_json({
                "type": "error",
                "message": "Invalid JSON"
            })
        except Exception as e:
            await self._send_json({
                "type": "error",
                "message": str(e)
            })

    async def handle_join(self, data):
        """Join a study group chat."""
        group_id = data.get("group_id")
        if not group_id:
            return

        # Verify user is a member of the group
        is_member = await self.verify_group_membership(group_id)
        
        if not is_member:
            await self._send_json({
                "type": "error",
                "message": "You are not a member of this group"
            })
            return

        self.group_id = group_id
        self.room_group_name = f"study_group_chat_{group_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self._send_json({
            "type": "joined",
            "group_id": group_id,
        })

    async def handle_typing(self, data):
        """Handle typing indicator in group."""
        if not self.room_group_name:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "group_typing",
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": data.get("is_typing", True),
            }
        )

    async def handle_message(self, data):
        """Handle sending a message to group."""
        if not self.room_group_name:
            await self._send_json({
                "type": "error",
                "message": "Not joined a group chat"
            })
            return

        message_body = data.get("message", "").strip()
        if not message_body:
            return

        # Save message
        message = await self.save_group_message(message_body)

        if message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "group_message",
                    "message_id": str(message.id),
                    "group_id": self.group_id,
                    "sender_id": self.user.id,
                    "sender_username": self.user.username,
                    "body": message_body,
                    "timestamp": message.created_at.isoformat(),
                }
            )

    async def group_message(self, event):
        """Handle incoming group message."""
        if event.get("sender_id") == self.user.id:
            return

        await self._send_json({
            "type": "message",
            "message_id": event.get("message_id"),
            "group_id": event.get("group_id"),
            "sender_id": event.get("sender_id"),
            "sender_username": event.get("sender_username"),
            "body": event.get("body"),
            "timestamp": event.get("timestamp"),
        })

    async def group_typing(self, event):
        """Handle typing indicator in group."""
        if event.get("user_id") == self.user.id:
            return

        await self._send_json({
            "type": "typing",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
            "is_typing": event.get("is_typing"),
        })

    @database_sync_to_async
    def verify_group_membership(self, group_id):
        """Verify user is a member of the study group."""
        from apps.social.models import StudyGroupMember

        return StudyGroupMember.objects.filter(
            user=self.user,
            group_id=group_id,
            status="active"
        ).exists()

    @database_sync_to_async
    def save_group_message(self, body):
        """Save message to database."""
        from apps.social.models import ConversationMessage, Conversation
        from apps.social.models import StudyGroup

        try:
            study_group = StudyGroup.objects.get(id=self.group_id)
            
            # Get or create a conversation for this group
            conversation, _ = Conversation.objects.get_or_create(
                name=f"Study Group: {study_group.name}",
                is_group=True,
            )
            conversation.members.add(self.user)

            message = ConversationMessage.objects.create(
                conversation=conversation,
                sender=self.user,
                body=body,
            )
            return message
        except StudyGroup.DoesNotExist:
            return None


class OnlineStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for user online status tracking.
    """

    async def _send_json(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload, default=str))

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()

        # Add to online users group
        await self.channel_layer.group_add("online_users", self.channel_name)

        # Broadcast that user is online
        await self.channel_layer.group_send(
            "online_users",
            {
                "type": "user_online",
                "user_id": self.user.id,
                "username": self.user.username,
                "online": True,
            }
        )

    async def disconnect(self, close_code):
        # Broadcast that user is offline
        if hasattr(self, 'user') and self.user:
            try:
                await self.channel_layer.group_send(
                    "online_users",
                    {
                        "type": "user_online",
                        "user_id": self.user.id,
                        "username": self.user.username,
                        "online": False,
                    }
                )
                await self.channel_layer.group_discard(
                    "online_users",
                    self.channel_name
                )
            except Exception:
                pass

    async def user_online(self, event):
        """Handle user online/offline status."""
        # Don't show own status to self
        if event.get("user_id") == self.user.id:
            return

        await self._send_json({
            "type": "status",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
            "online": event.get("online"),
        })


# Import timezone for read receipts
from django.utils import timezone