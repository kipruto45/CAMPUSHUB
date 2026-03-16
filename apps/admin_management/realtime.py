"""
Real-time WebSocket events for admin dashboard.
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from apps.activity.models import RecentActivity
from apps.resources.models import Resource
from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time admin dashboard updates.
    Provides live data for:
    - New user registrations
    - Resource uploads
    - Report submissions
    - System alerts
    - Moderation queue updates
    """

    async def connect(self):
        self.room_group_name = "admin_dashboard"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Connected to admin dashboard real-time feed"
        }))
        
        logger.info(f"Admin WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"Admin WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """Handle incoming messages from client."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            if message_type == "ping":
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "timestamp": timezone.now().isoformat()
                }))
            elif message_type == "subscribe":
                # Subscribe to specific event types
                event_types = data.get("events", [])
                await self.send(text_data=json.dumps({
                    "type": "subscribed",
                    "events": event_types
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }))

    # Handle messages from room group
    async def user_registered(self, event):
        """New user registration event."""
        await self.send(text_data=json.dumps({
            "type": "user_registered",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))

    async def resource_uploaded(self, event):
        """New resource uploaded event."""
        await self.send(text_data=json.dumps({
            "type": "resource_uploaded",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))

    async def report_submitted(self, event):
        """New report submitted event."""
        await self.send(text_data=json.dumps({
            "type": "report_submitted",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))

    async def system_alert(self, event):
        """System alert event."""
        await self.send(text_data=json.dumps({
            "type": "system_alert",
            "data": event["data"],
            "severity": event.get("severity", "info"),
            "timestamp": event["timestamp"]
        }))

    async def moderation_update(self, event):
        """Content moderation update event."""
        await self.send(text_data=json.dumps({
            "type": "moderation_update",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))

    async def analytics_update(self, event):
        """Real-time analytics update."""
        await self.send(text_data=json.dumps({
            "type": "analytics_update",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))

    async def notification_broadcast(self, event):
        """Broadcast notification to all admins."""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "data": event["data"],
            "timestamp": event["timestamp"]
        }))


class AdminRealtimeService:
    """
    Service class to broadcast real-time events to admin dashboard.
    Use this in your views/signals to push updates to connected admins.
    """
    
    @staticmethod
    async def broadcast_user_registration(user_data: dict):
        """Broadcast new user registration."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "user_registered",
            "data": user_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    async def broadcast_resource_upload(resource_data: dict):
        """Broadcast new resource upload."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "resource_uploaded",
            "data": resource_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    async def broadcast_report(report_data: dict):
        """Broadcast new report submission."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "report_submitted",
            "data": report_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    async def broadcast_system_alert(alert_data: dict, severity: str = "info"):
        """Broadcast system alert to admins."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "system_alert",
            "data": alert_data,
            "severity": severity,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    async def broadcast_moderation_update(moderation_data: dict):
        """Broadcast content moderation update."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "moderation_update",
            "data": moderation_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    async def broadcast_analytics(analytics_data: dict):
        """Broadcast real-time analytics update."""
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        await layer.group_send("admin_dashboard", {
            "type": "analytics_update",
            "data": analytics_data,
            "timestamp": timezone.now().isoformat()
        })


# Synchronous wrapper for use in Django signals
class AdminRealtimeServiceSync:
    """Synchronous wrapper for real-time service."""
    
    @staticmethod
    def broadcast_user_registration(user_data: dict):
        """Broadcast new user registration (sync version)."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        async_to_sync(layer.group_send)("admin_dashboard", {
            "type": "user_registered",
            "data": user_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    def broadcast_resource_upload(resource_data: dict):
        """Broadcast new resource upload (sync version)."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        async_to_sync(layer.group_send)("admin_dashboard", {
            "type": "resource_uploaded",
            "data": resource_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    def broadcast_report(report_data: dict):
        """Broadcast new report submission (sync version)."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        async_to_sync(layer.group_send)("admin_dashboard", {
            "type": "report_submitted",
            "data": report_data,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    def broadcast_system_alert(alert_data: dict, severity: str = "info"):
        """Broadcast system alert (sync version)."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        async_to_sync(layer.group_send)("admin_dashboard", {
            "type": "system_alert",
            "data": alert_data,
            "severity": severity,
            "timestamp": timezone.now().isoformat()
        })

    @staticmethod
    def broadcast_moderation_update(moderation_data: dict):
        """Broadcast moderation update (sync version)."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        layer = get_channel_layer()
        async_to_sync(layer.group_send)("admin_dashboard", {
            "type": "moderation_update",
            "data": moderation_data,
            "timestamp": timezone.now().isoformat()
        })
