"""
Live Study Rooms WebSocket Consumers
Real-time signaling for WebRTC video calls
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class StudyRoomConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for study room signaling"""
    
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.user = self.scope['user']
        self.room_group_name = f'study_room_{self.room_id}'
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark user as connected
        await self.mark_user_connected()
        
        # Notify others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name() or self.user.email,
            }
        )
    
    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Mark user as disconnected
            await self.mark_user_disconnected()
            
            # Notify others
            try:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_left',
                        'user_id': str(self.user.id),
                    }
                )
            except Exception:
                pass
    
    async def receive(self, text_data):
        """Handle incoming WebRTC signaling messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'offer':
                # WebRTC offer - forward to specific user
                await self.handle_offer(data)
            elif message_type == 'answer':
                # WebRTC answer - forward to specific user
                await self.handle_answer(data)
            elif message_type == 'ice_candidate':
                # ICE candidate - forward to specific user
                await self.handle_ice_candidate(data)
            elif message_type == 'chat_message':
                # Chat message
                await self.handle_chat_message(data)
            elif message_type == 'media_state':
                # Media state change (mute/unmute)
                await self.handle_media_state(data)
            elif message_type == 'screen_share':
                # Screen share state change
                await self.handle_screen_share(data)
            elif message_type == 'ping':
                # Keepalive
                await self.send(text_data=json.dumps({'type': 'pong'}))
                
        except Exception as e:
            logger.error(f"Error handling WebRTC message: {e}")
    
    async def handle_offer(self, data):
        """Handle WebRTC offer"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_offer',
                'offer': data.get('offer'),
                'sender_id': str(self.user.id),
                'target_id': data.get('target_id'),
            }
        )
    
    async def handle_answer(self, data):
        """Handle WebRTC answer"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_answer',
                'answer': data.get('answer'),
                'sender_id': str(self.user.id),
                'target_id': data.get('target_id'),
            }
        )
    
    async def handle_ice_candidate(self, data):
        """Handle ICE candidate"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_ice_candidate',
                'candidate': data.get('candidate'),
                'sender_id': str(self.user.id),
                'target_id': data.get('target_id'),
            }
        )
    
    async def handle_chat_message(self, data):
        """Handle chat message"""
        message = data.get('message', '')
        
        # Save to database
        await self.save_message(message)
        
        # Broadcast to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': str(self.user.id),
                'sender_name': self.user.get_full_name() or self.user.email,
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    async def handle_media_state(self, data):
        """Handle media state change"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'media_state',
                'user_id': str(self.user.id),
                'is_audio_enabled': data.get('is_audio_enabled', True),
                'is_video_enabled': data.get('is_video_enabled', True),
            }
        )
    
    async def handle_screen_share(self, data):
        """Handle screen share state change"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'screen_share',
                'user_id': str(self.user.id),
                'is_sharing': data.get('is_sharing', False),
            }
        )
    
    @database_sync_to_async
    def mark_user_connected(self):
        """Mark user as connected in the room"""
        try:
            from .models import RoomParticipant
            participant = RoomParticipant.objects.get(
                room_id=self.room_id,
                user=self.user
            )
            participant.status = RoomParticipant.Status.CONNECTED
            participant.save(update_fields=['status'])
        except RoomParticipant.DoesNotExist:
            pass
    
    @database_sync_to_async
    def mark_user_disconnected(self):
        """Mark user as disconnected in the room"""
        try:
            from .models import RoomParticipant
            participant = RoomParticipant.objects.get(
                room_id=self.room_id,
                user=self.user
            )
            participant.status = RoomParticipant.Status.DISCONNECTED
            participant.left_at = timezone.now()
            participant.save(update_fields=['status', 'left_at'])
        except RoomParticipant.DoesNotExist:
            pass
    
    @database_sync_to_async
    def save_message(self, message):
        """Save chat message to database"""
        from .models import RoomMessage, StudyRoom
        try:
            room = StudyRoom.objects.get(id=self.room_id)
            RoomMessage.objects.create(
                room=room,
                user=self.user,
                message=message
            )
        except StudyRoom.DoesNotExist:
            pass
    
    # WebSocket event handlers
    async def user_joined(self, event):
        """Handle user joined event"""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
        }))
    
    async def user_left(self, event):
        """Handle user left event"""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
        }))
    
    async def webrtc_offer(self, event):
        """Handle WebRTC offer"""
        if event.get('target_id') == str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'offer': event['offer'],
                'sender_id': event['sender_id'],
            }))
    
    async def webrtc_answer(self, event):
        """Handle WebRTC answer"""
        if event.get('target_id') == str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'sender_id': event['sender_id'],
            }))
    
    async def webrtc_ice_candidate(self, event):
        """Handle ICE candidate"""
        if event.get('target_id') == str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'sender_id': event['sender_id'],
            }))
    
    async def chat_message(self, event):
        """Handle chat message"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
        }))
    
    async def media_state(self, event):
        """Handle media state change"""
        await self.send(text_data=json.dumps({
            'type': 'media_state',
            'user_id': event['user_id'],
            'is_audio_enabled': event['is_audio_enabled'],
            'is_video_enabled': event['is_video_enabled'],
        }))
    
    async def screen_share(self, event):
        """Handle screen share state change"""
        await self.send(text_data=json.dumps({
            'type': 'screen_share',
            'user_id': event['user_id'],
            'is_sharing': event['is_sharing'],
        }))
