"""
Enriched Push Notification Service for CampusHub.
Provides rich notifications with actionable buttons, images, and deep linking.
Supports both APNs (Apple) and FCM (Google) payload formats.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationActionType(Enum):
    """Types of notification actions."""
    VIEW = "view"
    DISMISS = "dismiss"
    REPLY = "reply"
    OPEN_URL = "open_url"
    CUSTOM = "custom"


class NotificationImageType(Enum):
    """Types of notification images."""
    ICON = "icon"
    THUMBNAIL = "thumbnail"
    HERO = "hero"


@dataclass
class NotificationAction:
    """Represents an action button in a rich notification."""
    action_type: NotificationActionType
    title: str
    icon: str = ""  # SF Symbol name (iOS) or drawable name (Android)
    action_id: str = ""
    foreground: bool = True
    authentication_required: bool = False
    destructive: bool = False


@dataclass
class NotificationImage:
    """Represents an image in a rich notification."""
    image_type: NotificationImageType
    url: str
    width: int = 0
    height: int = 0
    accessibility_text: str = ""


@dataclass
class EnrichedNotification:
    """
    Data class for enriched push notifications.
    Supports rich features like action buttons, images, and deep linking.
    """
    # Basic notification fields
    title: str
    body: str
    subtitle: str = ""
    
    # Action buttons
    actions: List[NotificationAction] = field(default_factory=list)
    
    # Rich media
    image: Optional[NotificationImage] = None
    icon: Optional[NotificationImage] = None
    
    # Deep linking
    deep_link: str = ""
    fallback_url: str = ""
    
    # Metadata
    thread_id: str = ""
    category: str = ""
    priority: str = "normal"
    
    # Custom data payload
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Target identifiers
    target_type: str = ""  # resource, announcement, profile, etc.
    target_id: str = ""


class EnrichedNotificationService:
    """
    Service for building and sending enriched push notifications.
    
    Supports:
    - Rich notifications with action buttons (View, Dismiss, Reply)
    - Notification images (icons, thumbnails, hero images)
    - Deep linking from notifications
    - APNs (Apple) and FCM (Google) payload formats
    - Notification categories for iOS actionable notifications
    """

    # Default action button configurations
    DEFAULT_ACTIONS = {
        "view": NotificationAction(
            action_type=NotificationActionType.VIEW,
            title="View",
            icon="eye",
            action_id="VIEW_ACTION",
            foreground=True,
        ),
        "dismiss": NotificationAction(
            action_type=NotificationActionType.DISMISS,
            title="Dismiss",
            icon="xmark",
            action_id="DISMISS_ACTION",
            foreground=False,
            destructive=True,
        ),
        "reply": NotificationAction(
            action_type=NotificationActionType.REPLY,
            title="Reply",
            icon="arrowshape.turn.up.left",
            action_id="REPLY_ACTION",
            foreground=True,
            authentication_required=True,
        ),
    }

    # Category identifiers for iOS
    CATEGORIES = {
        "RESOURCE": "RESOURCE_NOTIFICATION",
        "ANNOUNCEMENT": "ANNOUNCEMENT_NOTIFICATION",
        "MESSAGE": "MESSAGE_NOTIFICATION",
        "SYSTEM": "SYSTEM_NOTIFICATION",
        "DEFAULT": "DEFAULT_NOTIFICATION",
    }

    def __init__(self):
        self._apns_service = None
        self._fcm_service = None

    @property
    def apns_service(self):
        """Lazy load APNs service."""
        if self._apns_service is None:
            try:
                from .apns import APNsService, APNsNotification
                self._apns_service = APNsService()
            except Exception as e:
                logger.warning(f"APNs service not available: {e}")
                self._apns_service = None
        return self._apns_service

    @property
    def fcm_service(self):
        """Lazy load FCM service."""
        if self._fcm_service is None:
            try:
                from .fcm import FCMService, PushNotification
                self._fcm_service = FCMService()
            except Exception as e:
                logger.warning(f"FCM service not available: {e}")
                self._fcm_service = None
        return self._fcm_service

    def _build_apns_payload(self, notification: EnrichedNotification) -> Dict[str, Any]:
        """Build APNs payload for rich notification."""
        from .apns import APNsNotification as NativeAPNsNotification
        
        # Build alert payload
        alert = {
            "title": notification.title,
            "body": notification.body,
        }
        if notification.subtitle:
            alert["subtitle"] = notification.subtitle

        # Create base APNs notification
        apns_notification = NativeAPNsNotification(
            title=notification.title,
            body=notification.body,
            subtitle=notification.subtitle or None,
            category=notification.category or self._get_category(notification.target_type),
            sound="default",
            mutable_content=True,
            data=notification.data.copy() if notification.data else {},
        )

        # Add deep link to data payload
        if notification.deep_link:
            apns_notification.data["deep_link"] = notification.deep_link
            apns_notification.data["fallback_url"] = notification.fallback_url
            apns_notification.data["target_type"] = notification.target_type
            apns_notification.data["target_id"] = notification.target_id

        # Build the full payload
        payload = {
            "aps": {
                "alert": alert,
                "sound": "default",
                "mutable-content": 1,
            }
        }

        # Add badge if provided
        if notification.data.get("badge"):
            payload["aps"]["badge"] = notification.data["badge"]

        # Add category for actionable notifications
        if notification.category or notification.actions:
            category = notification.category or self._get_category(notification.target_type)
            payload["aps"]["category"] = category

        # Add thread ID for grouping
        if notification.thread_id:
            payload["aps"]["thread-id"] = notification.thread_id

        # Add custom data
        if notification.data:
            for key, value in notification.data.items():
                if key not in ["badge"]:
                    payload[key] = value

        return payload

    def _build_fcm_payload(self, notification: EnrichedNotification) -> Dict[str, Any]:
        """Build FCM payload for rich notification."""
        from .fcm import PushNotification as NativePushNotification
        from .fcm import NotificationPriority

        # Determine priority
        fcm_priority = (
            NotificationPriority.HIGH 
            if notification.priority == "high" 
            else NotificationPriority.NORMAL
        )

        # Create FCM notification
        fcm_notification = NativePushNotification(
            title=notification.title,
            body=notification.body,
            priority=fcm_priority,
            data=notification.data.copy() if notification.data else {},
        )

        # Add image URL if available
        if notification.image:
            fcm_notification.data["image_url"] = notification.image.url
            fcm_notification.data["image_type"] = notification.image.image_type.value

        # Add deep link to data
        if notification.deep_link:
            fcm_notification.data["deep_link"] = notification.deep_link
            fcm_notification.data["fallback_url"] = notification.fallback_url

        # Add target info
        fcm_notification.data["target_type"] = notification.target_type
        fcm_notification.data["target_id"] = notification.target_id

        # Build the full payload
        payload = {
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "priority": fcm_priority.value,
            "data": fcm_notification.data,
        }

        # Add image
        if notification.image:
            payload["notification"]["image"] = notification.image.url

        # Add Android-specific configuration for rich notifications
        android_config = {
            "notification": {
                "channel_id": f"campushub_{notification.target_type or 'default'}",
                "priority": "high" if notification.priority == "high" else "default",
            }
        }

        if notification.image:
            android_config["notification"]["image_url"] = notification.image.url

        payload["android"] = android_config

        # Add APNs configuration for iOS
        apns_config = {
            "headers": {}
        }

        if notification.thread_id:
            apns_config["headers"]["thread-id"] = notification.thread_id

        if notification.category or notification.actions:
            apns_config["payload"] = {
                "aps": {
                    "category": notification.category or self._get_category(notification.target_type)
                }
            }

        payload["apns"] = apns_config

        return payload

    def _get_category(self, target_type: str) -> str:
        """Get notification category based on target type."""
        mapping = {
            "resource": self.CATEGORIES["RESOURCE"],
            "announcement": self.CATEGORIES["ANNOUNCEMENT"],
            "message": self.CATEGORIES["MESSAGE"],
            "system": self.CATEGORIES["SYSTEM"],
        }
        return mapping.get(target_type.lower(), self.CATEGORIES["DEFAULT"])

    def _build_deep_link(self, target_type: str, target_id: str, action: str = "view") -> str:
        """Build deep link URL for notification."""
        scheme = getattr(settings, "MOBILE_DEEPLINK_SCHEME", "campushub")
        host = getattr(settings, "MOBILE_DEEPLINK_HOST", "campushub.com")

        # Build path based on target type
        path_mapping = {
            "resource": f"resources/{target_id}",
            "announcement": f"announcements/{target_id}",
            "profile": f"profile/{target_id}",
            "course": f"courses/{target_id}",
            "unit": f"units/{target_id}",
        }

        path = path_mapping.get(target_type.lower(), f"{target_type}/{target_id}")

        # Return universal link format
        return f"https://{host}/{path}"

    def send_enriched_notification(
        self,
        tokens: List[str],
        notification: EnrichedNotification,
        platform: str = "both",
    ) -> Dict[str, Any]:
        """
        Send enriched notification to device tokens.
        
        Args:
            tokens: List of device tokens
            notification: EnrichedNotification instance
            platform: "ios", "android", or "both"
            
        Returns:
            Dict with success status and results
        """
        results = {"ios": {}, "android": {}}

        # Send to iOS devices
        if platform in ["ios", "both"]:
            ios_tokens = [t for t in tokens if not self._is_android_fcm_token(t)]
            if ios_tokens and self.apns_service:
                try:
                    from .apns import APNsNotification
                    apns_notif = APNsNotification(
                        title=notification.title,
                        body=notification.body,
                        subtitle=notification.subtitle or None,
                        category=notification.category or self._get_category(notification.target_type),
                        data=notification.data.copy() if notification.data else {},
                    )
                    results["ios"] = self.apns_service.send_to_tokens(ios_tokens, apns_notif)
                except Exception as e:
                    logger.error(f"Failed to send iOS notification: {e}")
                    results["ios"] = {"success": 0, "failed": len(ios_tokens), "errors": [str(e)]}

        # Send to Android devices
        if platform in ["android", "both"]:
            android_tokens = [t for t in tokens if self._is_android_fcm_token(t)]
            if android_tokens and self.fcm_service:
                try:
                    from .fcm import PushNotification, NotificationPriority
                    priority = (
                        NotificationPriority.HIGH 
                        if notification.priority == "high" 
                        else NotificationPriority.NORMAL
                    )
                    fcm_notif = PushNotification(
                        title=notification.title,
                        body=notification.body,
                        priority=priority,
                        data=notification.data.copy() if notification.data else {},
                    )
                    # Add image to data if present
                    if notification.image:
                        fcm_notif.data["image_url"] = notification.image.url
                    if notification.deep_link:
                        fcm_notif.data["deep_link"] = notification.deep_link
                    results["android"] = self.fcm_service.send_to_tokens(android_tokens, fcm_notif)
                except Exception as e:
                    logger.error(f"Failed to send Android notification: {e}")
                    results["android"] = {"success": 0, "failed": len(android_tokens), "errors": [str(e)]}

        return results

    def _is_android_fcm_token(self, token: str) -> bool:
        """Check if token is likely an Android FCM token."""
        # FCM tokens don't start with specific prefixes like iOS
        # This is a simple heuristic
        return not token.startswith("APNs")

    def create_resource_notification(
        self,
        user_tokens: List[str],
        resource_title: str,
        resource_id: str,
        action: str,
        sender_name: str = "",
    ) -> Dict[str, Any]:
        """Create and send a rich notification for a resource."""
        
        # Build notification content based on action
        action_messages = {
            "approved": f'Your resource "{resource_title}" has been approved!',
            "rejected": f'Your resource "{resource_title}" was rejected.',
            "comment": f'{sender_name} commented on "{resource_title}"',
            "like": f'{sender_name} liked "{resource_title}"',
            "download": f'Someone downloaded "{resource_title}"',
            "share": f'{sender_name} shared "{resource_title}" with you',
        }

        title = f"Resource {action.capitalize()}"
        body = action_messages.get(action, f'Resource "{resource_title}" was {action}')

        notification = EnrichedNotification(
            title=title,
            body=body,
            target_type="resource",
            target_id=resource_id,
            deep_link=self._build_deep_link("resource", resource_id),
            fallback_url=f"/resources/{resource_id}/",
            thread_id=f"resource_{resource_id}",
            category=self.CATEGORIES["RESOURCE"],
            actions=[
                self.DEFAULT_ACTIONS["view"],
                self.DEFAULT_ACTIONS["dismiss"],
            ],
            data={
                "resource_id": resource_id,
                "action": action,
                "type": "resource_notification",
            },
        )

        return self.send_enriched_notification(user_tokens, notification)

    def create_announcement_notification(
        self,
        user_tokens: List[str],
        announcement_title: str,
        announcement_id: str,
        sender_name: str = "",
    ) -> Dict[str, Any]:
        """Create and send a rich notification for an announcement."""
        
        notification = EnrichedNotification(
            title="New Announcement",
            body=f'{sender_name}: {announcement_title}',
            target_type="announcement",
            target_id=announcement_id,
            deep_link=self._build_deep_link("announcement", announcement_id),
            fallback_url=f"/announcements/{announcement_id}/",
            thread_id="announcements",
            category=self.CATEGORIES["ANNOUNCEMENT"],
            actions=[
                self.DEFAULT_ACTIONS["view"],
                self.DEFAULT_ACTIONS["dismiss"],
            ],
            data={
                "announcement_id": announcement_id,
                "type": "announcement_notification",
            },
        )

        return self.send_enriched_notification(user_tokens, notification)

    def create_system_notification(
        self,
        user_tokens: List[str],
        title: str,
        message: str,
        target_type: str = "",
        target_id: str = "",
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Create and send a system notification."""
        
        notification = EnrichedNotification(
            title=title,
            body=message,
            target_type=target_type,
            target_id=target_id,
            priority=priority,
            deep_link=self._build_deep_link(target_type, target_id) if target_id else "",
            category=self.CATEGORIES["SYSTEM"],
            actions=[
                self.DEFAULT_ACTIONS["view"],
                self.DEFAULT_ACTIONS["dismiss"],
            ],
            data={
                "target_type": target_type,
                "target_id": target_id,
                "type": "system_notification",
            },
        )

        return self.send_enriched_notification(user_tokens, notification)


# Singleton instance
enriched_notification_service = EnrichedNotificationService()


# Convenience functions
def send_enriched_push(
    tokens: List[str],
    title: str,
    body: str,
    target_type: str = "",
    target_id: str = "",
    deep_link: str = "",
    actions: List[NotificationAction] = None,
    image: NotificationImage = None,
    platform: str = "both",
    **kwargs,
) -> Dict[str, Any]:
    """Send an enriched push notification."""
    notification = EnrichedNotification(
        title=title,
        body=body,
        target_type=target_type,
        target_id=target_id,
        deep_link=deep_link or f"campushub://{target_type}/{target_id}",
        actions=actions or [ EnrichedNotificationService.DEFAULT_ACTIONS["view"], EnrichedNotificationService.DEFAULT_ACTIONS["dismiss"] ],
        image=image,
        data=kwargs,
    )
    return enriched_notification_service.send_enriched_notification(tokens, notification, platform)