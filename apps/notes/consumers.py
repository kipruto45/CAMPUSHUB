"""
Notes WebSocket Consumers for CampusHub
Real-time collaborative editing
"""

import json
import asyncio
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import Note, NotePresence, NoteLock
from .services import NoteService, CollaborationService

User = get_user_model()


class NoteConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time collaborative note editing.
    
    Handles:
    - note:update - Note content changed
    - note:cursor - Cursor position changed
    - note:presence - User joined/left
    - note:lock - Note locked for editing
    """
    
    async def _send_json(self, payload: dict) -> None:
        """Send JSON payloads safely."""
        await self.send(text_data=json.dumps(payload, default=str))
    
    async def connect(self):
        self.user = self.scope.get("user")
        self.note_id = None
        self.room_group_name = None
        
        # Only authenticated users can connect
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle disconnection and cleanup."""
        if self.note_id and self.room_group_name:
            # Remove from channel layer group
            try:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            except Exception:
                pass
            
            # Mark user as offline
            await self._set_offline()
            
            # Release any lock held by this user
            await self._release_lock()
            
            # Broadcast presence update
            await self._broadcast_presence('left')
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            if message_type == "join":
                await self.handle_join(data)
            elif message_type == "leave":
                await self.handle_leave(data)
            elif message_type == "note:update":
                await self.handle_note_update(data)
            elif message_type == "note:cursor":
                await self.handle_cursor_update(data)
            elif message_type == "note:lock":
                await self.handle_lock_request(data)
            elif message_type == "note:unlock":
                await self.handle_unlock_request(data)
            elif message_type == "ping":
                await self._send_json({"type": "pong"})
                
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
        """Join a note's collaboration room."""
        self.note_id = data.get("note_id")
        
        if not self.note_id:
            await self._send_json({
                "type": "error",
                "message": "note_id is required"
            })
            return
        
        # Verify user has access to the note
        has_access = await self._check_note_access()
        
        if not has_access:
            await self._send_json({
                "type": "error",
                "message": "You do not have access to this note"
            })
            await self.close()
            return
        
        # Set up room group
        self.room_group_name = f"note_{self.note_id}"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Update presence
        await self._update_presence('viewing')
        
        # Broadcast presence
        await self._broadcast_presence('joined')
        
        # Send current state to the user
        await self._send_current_state()
        
        await self._send_json({
            "type": "joined",
            "note_id": str(self.note_id),
            "room": self.room_group_name,
        })
    
    async def handle_leave(self, data):
        """Leave the note's collaboration room."""
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            await self._set_offline()
            await self._broadcast_presence('left')
            
            self.note_id = None
            self.room_group_name = None
    
    async def handle_note_update(self, data):
        """Handle note content update."""
        if not self.room_group_name:
            await self._send_json({
                "type": "error",
                "message": "Not joined a note room"
            })
            return
        
        # Check if user can edit
        can_edit = await self._check_note_edit_permission()
        
        if not can_edit:
            await self._send_json({
                "type": "error",
                "message": "You do not have permission to edit this note"
            })
            return
        
        # Check for lock
        has_lock = await self._check_lock()
        
        if not has_lock:
            await self._send_json({
                "type": "error",
                "message": "Note is not locked for editing"
            })
            return
        
        # Get updated content
        content = data.get("content")
        content_html = data.get("content_html")
        title = data.get("title")
        
        # Update the note
        updated = await self._update_note(content, content_html, title)
        
        if updated:
            # Broadcast the update to all collaborators
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "note_updated",
                    "note_id": str(self.note_id),
                    "content": content,
                    "content_html": content_html,
                    "title": title,
                    "updated_by": self.user.username,
                    "timestamp": timezone.now().isoformat(),
                }
            )
    
    async def handle_cursor_update(self, data):
        """Handle cursor position update."""
        if not self.room_group_name:
            return
        
        cursor_position = data.get("cursor_position", 0)
        cursor_selection = data.get("cursor_selection", {})
        
        # Update presence with cursor position
        await self._update_presence(
            activity='editing',
            cursor_position=cursor_position,
            cursor_selection=cursor_selection
        )
        
        # Broadcast cursor position to other users
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "cursor_updated",
                "user_id": str(self.user.id),
                "username": self.user.username,
                "cursor_position": cursor_position,
                "cursor_selection": cursor_selection,
            }
        )
    
    async def handle_lock_request(self, data):
        """Request to lock a note for editing."""
        if not self.room_group_name:
            await self._send_json({
                "type": "error",
                "message": "Not joined a note room"
            })
            return
        
        # Check if user can edit
        can_edit = await self._check_note_edit_permission()
        
        if not can_edit:
            await self._send_json({
                "type": "error",
                "message": "You do not have permission to edit this note"
            })
            return
        
        lock, created = await self._acquire_lock()
        
        if not lock:
            # Get current lock info
            current_lock = await self._get_current_lock()
            await self._send_json({
                "type": "note:lock",
                "locked": True,
                "locked_by": current_lock.get("user_username") if current_lock else None,
                "message": "Note is locked by another user"
            })
            return
        
        # Broadcast lock acquisition
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "lock_acquired",
                "user_id": str(self.user.id),
                "username": self.user.username,
            }
        )
        
        await self._send_json({
            "type": "note:lock",
            "locked": True,
            "locked_by": self.user.username,
        })
    
    async def handle_unlock_request(self, data):
        """Release the lock on a note."""
        if not self.room_group_name:
            return
        
        await self._release_lock()
        
        # Broadcast lock release
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "lock_released",
                "user_id": str(self.user.id),
                "username": self.user.username,
            }
        )
        
        await self._send_json({
            "type": "note:lock",
            "locked": False,
        })
    
    # Channel layer handlers
    
    async def note_updated(self, event):
        """Handle note update from group."""
        # Don't send back to sender
        if event.get("updated_by") == self.user.username:
            return
        
        await self._send_json({
            "type": "note:update",
            "note_id": event.get("note_id"),
            "content": event.get("content"),
            "content_html": event.get("content_html"),
            "title": event.get("title"),
            "updated_by": event.get("updated_by"),
            "timestamp": event.get("timestamp"),
        })
    
    async def cursor_updated(self, event):
        """Handle cursor update from group."""
        # Don't send back to sender
        if event.get("user_id") == str(self.user.id):
            return
        
        await self._send_json({
            "type": "note:cursor",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
            "cursor_position": event.get("cursor_position"),
            "cursor_selection": event.get("cursor_selection"),
        })
    
    async def user_joined(self, event):
        """Handle user joined from group."""
        await self._send_json({
            "type": "note:presence",
            "action": "joined",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
        })
    
    async def user_left(self, event):
        """Handle user left from group."""
        await self._send_json({
            "type": "note:presence",
            "action": "left",
            "user_id": event.get("user_id"),
            "username": event.get("username"),
        })
    
    async def lock_acquired(self, event):
        """Handle lock acquired from group."""
        await self._send_json({
            "type": "note:lock",
            "locked": True,
            "locked_by": event.get("username"),
        })
    
    async def lock_released(self, event):
        """Handle lock released from group."""
        await self._send_json({
            "type": "note:lock",
            "locked": False,
        })
    
    # Database operations
    
    @database_sync_to_async
    def _check_note_access(self):
        """Check if user has access to the note."""
        try:
            note = Note.objects.get(id=self.note_id)
            return NoteService.can_view_note(self.user, note)
        except Note.DoesNotExist:
            return False
    
    @database_sync_to_async
    def _check_note_edit_permission(self):
        """Check if user can edit the note."""
        try:
            note = Note.objects.get(id=self.note_id)
            return NoteService.can_edit_note(self.user, note)
        except Note.DoesNotExist:
            return False
    
    @database_sync_to_async
    def _update_note(self, content, content_html, title):
        """Update the note content."""
        try:
            note = Note.objects.get(id=self.note_id)
            
            if content is not None:
                note.content = content
            if content_html is not None:
                note.content_html = content_html
            if title is not None:
                note.title = title
            
            note.save()
            return True
        except Note.DoesNotExist:
            return False
    
    @database_sync_to_async
    def _update_presence(self, activity=None, cursor_position=None, cursor_selection=None):
        """Update user presence."""
        try:
            note = Note.objects.get(id=self.note_id)
            CollaborationService.update_presence(
                note=note,
                user=self.user,
                activity=activity,
                cursor_position=cursor_position,
                cursor_selection=cursor_selection
            )
        except Note.DoesNotExist:
            pass
    
    @database_sync_to_async
    def _set_offline(self):
        """Mark user as offline."""
        try:
            note = Note.objects.get(id=self.note_id)
            CollaborationService.set_offline(note, self.user)
        except Note.DoesNotExist:
            pass
    
    @database_sync_to_async
    def _acquire_lock(self):
        """Acquire a lock on the note."""
        try:
            note = Note.objects.get(id=self.note_id)
            return CollaborationService.acquire_lock(note, self.user)
        except Note.DoesNotExist:
            return None, False
    
    @database_sync_to_async
    def _release_lock(self):
        """Release the lock on the note."""
        try:
            note = Note.objects.get(id=self.note_id)
            CollaborationService.release_lock(note, self.user)
        except Note.DoesNotExist:
            pass
    
    @database_sync_to_async
    def _check_lock(self):
        """Check if note is locked by current user."""
        try:
            note = Note.objects.get(id=self.note_id)
            lock = CollaborationService.check_lock(note)
            return lock and lock.user == self.user
        except Note.DoesNotExist:
            return False
    
    @database_sync_to_async
    def _get_current_lock(self):
        """Get current lock info."""
        try:
            note = Note.objects.get(id=self.note_id)
            lock = CollaborationService.check_lock(note)
            if lock:
                return {
                    "user_id": str(lock.user.id),
                    "user_username": lock.user.username,
                }
            return None
        except Note.DoesNotExist:
            return None
    
    async def _send_current_state(self):
        """Send current note state to the user."""
        note_data = await self._get_note_data()
        
        if note_data:
            await self._send_json({
                "type": "current_state",
                "note": note_data.get("note"),
                "presence": note_data.get("presence", []),
                "lock": note_data.get("lock"),
            })
    
    @database_sync_to_async
    def _get_note_data(self):
        """Get note data for current state."""
        try:
            note = Note.objects.get(id=self.note_id)
            
            # Get active presence
            threshold = timezone.now() - timedelta(minutes=5)
            presence = NotePresence.objects.filter(
                note=note,
                is_online=True,
                last_active__gte=threshold
            ).select_related('user')
            
            presence_data = []
            for p in presence:
                presence_data.append({
                    "user_id": str(p.user.id),
                    "username": p.user.username,
                    "activity": p.activity,
                    "cursor_position": p.cursor_position,
                    "cursor_selection": p.cursor_selection,
                })
            
            # Get current lock
            lock = CollaborationService.check_lock(note)
            lock_data = None
            if lock:
                lock_data = {
                    "user_id": str(lock.user.id),
                    "username": lock.user.username,
                    "expires_at": lock.expires_at.isoformat(),
                }
            
            return {
                "note": {
                    "id": str(note.id),
                    "title": note.title,
                    "content": note.content,
                    "content_html": note.content_html,
                },
                "presence": presence_data,
                "lock": lock_data,
            }
        except Note.DoesNotExist:
            return None
    
    async def _broadcast_presence(self, action):
        """Broadcast presence update to the group."""
        if not self.room_group_name:
            return
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": f"user_{action}",
                "user_id": str(self.user.id),
                "username": self.user.username,
            }
        )
