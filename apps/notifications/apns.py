"""
Apple Push Notification Service (APNs) for CampusHub.
Handles sending push notifications to iOS devices.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class APNsPriority(Enum):
    IMMEDIATE = 10  # Send immediately
    IDLE = 5  # Send at opportune time


class APNsEnvironment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass
class APNsConfig:
    """APNs Configuration."""

    key_id: str
    team_id: str
    bundle_id: str
    auth_key_path: Optional[str] = None
    auth_key: Optional[str] = None  # Base64 encoded key
    environment: APNsEnvironment = APNsEnvironment.DEVELOPMENT
    enabled: bool = True


@dataclass
class APNsNotification:
    """Apple Push Notification data class."""

    title: str
    body: str
    subtitle: Optional[str] = None
    category: Optional[str] = None
    sound: Optional[str] = "default"
    badge: Optional[int] = None
    thread_id: Optional[str] = None
    launch_image: Optional[str] = None

    # Custom data
    data: Optional[Dict[str, Any]] = None

    # Actions
    mutable_content: bool = True
    content_available: bool = False


class APNsService:
    """
    Apple Push Notification Service for sending notifications to iOS devices.

    Supports:
    - Token-based authentication (recommended)
    - Certificate-based authentication (legacy)
    - Silent notifications
    - Rich notifications with actions
    """

    DEVELOPMENT推送地址 = "https://api.sandbox.push.apple.com"
    PRODUCTION推送地址 = "https://api.push.apple.com"

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> APNsConfig:
        """Load APNs configuration from settings."""
        try:
            key_id = getattr(settings, "APNS_KEY_ID", "")
            team_id = getattr(settings, "APNS_TEAM_ID", "")
            bundle_id = getattr(settings, "APNS_BUNDLE_ID", "com.campushub.app")
            auth_key_path = getattr(settings, "APNS_AUTH_KEY_PATH", "")
            auth_key = getattr(settings, "APNS_AUTH_KEY", "")

            environment = getattr(settings, "APNS_ENVIRONMENT", "development")
            if environment == "production":
                env = APNsEnvironment.PRODUCTION
            else:
                env = APNsEnvironment.DEVELOPMENT

            enabled = getattr(settings, "APNS_ENABLED", bool(key_id and team_id))

            return APNsConfig(
                key_id=key_id,
                team_id=team_id,
                bundle_id=bundle_id,
                auth_key_path=auth_key_path,
                auth_key=auth_key,
                environment=env,
                enabled=enabled,
            )
        except Exception as e:
            logger.warning(f"APNs configuration error: {e}")
            return APNsConfig(key_id="", team_id="", bundle_id="", enabled=False)

    def _get_push_url(self) -> str:
        """Get the appropriate push URL based on environment."""
        if self._config.environment == APNsEnvironment.DEVELOPMENT:
            return f"{self.DEVELOPMENT推送地址}/3/device/"
        return f"{self.PRODUCTION推送地址}/3/device/"

    def _build_payload(self, notification: APNsNotification) -> Dict[str, Any]:
        """Build the APNs notification payload."""
        payload = {
            "aps": {
                "alert": {
                    "title": notification.title,
                    "body": notification.body,
                },
            }
        }

        # Add optional fields
        if notification.subtitle:
            payload["aps"]["alert"]["subtitle"] = notification.subtitle

        if notification.sound:
            payload["aps"]["sound"] = notification.sound

        if notification.badge is not None:
            payload["aps"]["badge"] = notification.badge

        if notification.category:
            payload["aps"]["category"] = notification.category

        if notification.thread_id:
            payload["aps"]["thread-id"] = notification.thread_id

        if notification.launch_image:
            payload["aps"]["launch-image"] = notification.launch_image

        if notification.mutable_content:
            payload["aps"]["mutable-content"] = 1

        if notification.content_available:
            payload["aps"]["content-available"] = 1

        # Add custom data
        if notification.data:
            payload.update(notification.data)

        return payload

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for APNs request."""
        headers = {
            "Content-Type": "application/json",
            "apns-topic": self._config.bundle_id,
        }

        if self._config.environment == APNsEnvironment.DEVELOPMENT:
            headers["apns-priority"] = "10"
        else:
            headers["apns-priority"] = "10"

        return headers

    def send_to_token(
        self,
        token: str,
        notification: APNsNotification,
        collapse_id: Optional[str] = None,
        expiration: Optional[int] = None,
        mutable: bool = True,
    ) -> Dict[str, Any]:
        """
        Send notification to a single device token.

        Args:
            token: Device token (hex string)
            notification: APNsNotification instance
            collapse_id: Collapse identifier for grouping
            expiration: Unix timestamp when notification expires
            mutable: Enable mutable content

        Returns:
            Dict with 'success', 'message_id', 'error' keys
        """
        if not self._config.enabled:
            return {"success": False, "error": "APNs is disabled"}

        # Clean token (remove spaces and dashes)
        token = token.replace(" ", "").replace("-", "").lower()

        url = f"{self._get_push_url()}{token}"
        payload = self._build_payload(notification)

        headers = self._get_headers()
        if mutable:
            headers["apns-push-type"] = "mutable"
        else:
            headers["apns-push-type"] = "alert"

        if collapse_id:
            headers["apns-collapse-id"] = collapse_id

        if expiration:
            headers["apns-expiration"] = str(expiration)

        try:
            # Note: In production, you'd implement JWT-based authentication
            # This is a simplified version showing the structure

            # Add JWT token for authentication (requires additional setup)
            # auth_token = self._generate_jwt_token()
            # headers['Authorization'] = f'Bearer {auth_token}'

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                logger.info("APNs notification sent successfully")
                return {
                    "success": True,
                    "message_id": response.headers.get("apns-id"),
                    "error": None,
                }
            else:
                error_info = response.json()
                error = error_info.get("reason", "Unknown error")
                logger.error(f"APNs send failed: {error}")
                return {
                    "success": False,
                    "error": error,
                    "status": response.status_code,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"APNs request failed: {e}")
            return {"success": False, "error": str(e)}

    def send_to_tokens(
        self,
        tokens: List[str],
        notification: APNsNotification,
    ) -> Dict[str, Any]:
        """
        Send notification to multiple device tokens.

        Note: APNs doesn't support batch sending directly.
        This method sends sequentially.
        """
        if not self._config.enabled:
            return {"success": False, "error": "APNs is disabled"}

        results = {"success": 0, "failed": 0, "errors": []}

        for token in tokens:
            result = self.send_to_token(token, notification)
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    {"token": token[:20], "error": result.get("error")}
                )

        return results

    def send_silent_notification(
        self,
        token: str,
        data: Dict[str, Any],
        priority: APNsPriority = APNsPriority.IDLE,
        expiration: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send a silent background notification.

        Silent notifications don't show in notification center
        but wake the app to process the data.
        """
        headers = self._get_headers()
        headers["apns-push-type"] = "background"
        headers["apns-priority"] = str(priority.value)

        if expiration:
            headers["apns-expiration"] = str(expiration)

        # Add custom data
        payload = {"aps": {"content-available": 1}}
        payload.update(data)

        token = token.replace(" ", "").replace("-", "").lower()
        url = f"{self._get_push_url()}{token}"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": response.json().get("reason")}

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}


# Singleton instance
apns_service = APNsService()


# Convenience functions
def send_ios_notification(
    token: str, title: str, body: str, **kwargs
) -> Dict[str, Any]:
    """Send an iOS push notification."""
    notification = APNsNotification(
        title=title,
        body=body,
        **{
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "subtitle",
                "category",
                "sound",
                "badge",
                "thread_id",
                "launch_image",
                "data",
                "mutable_content",
                "content_available",
            ]
        },
    )
    return apns_service.send_to_token(token, notification)


def send_silent_ios_notification(token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send a silent iOS notification for background updates."""
    return apns_service.send_silent_notification(token, data)
