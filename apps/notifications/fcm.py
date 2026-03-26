"""
Firebase Cloud Messaging (FCM) Service for CampusHub.
Handles sending push notifications to Android, iOS, and web clients.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    HIGH = "high"
    NORMAL = "normal"


class NotificationType(Enum):
    INDIVIDUAL = "individual"
    TOPIC = "topic"
    CONDITION = "condition"


@dataclass
class FCMConfig:
    """FCM Configuration."""

    server_key: str
    project_id: str
    enabled: bool = True
    service_account_path: str = ""


@dataclass
class PushNotification:
    """Push notification data class."""

    title: str
    body: str
    icon: Optional[str] = None
    sound: Optional[str] = "default"
    badge: Optional[int] = None
    tag: Optional[str] = None
    color: Optional[str] = None
    click_action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.HIGH
    time_to_live: int = 3600  # 1 hour


class FCMService:
    """
    Firebase Cloud Messaging Service for sending push notifications.

    Usage:
        fcm = FCMService()
        fcm.send_to_token(token, PushNotification(title="Hello", body="World"))
    """

    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    def __init__(self):
        self._config = self._load_config()
        self._access_token = None
        self._token_expiry = None

    def _load_config(self) -> FCMConfig:
        """Load FCM configuration from settings."""
        try:
            server_key = getattr(settings, "FCM_SERVER_KEY", None)
            if server_key is None:
                # Try environment variable
                server_key = os.environ.get("FCM_SERVER_KEY", "")

            project_id = getattr(settings, "FCM_PROJECT_ID", "campushub-80677")

            # Check for service account file path
            service_account_path = getattr(settings, "FCM_SERVICE_ACCOUNT_PATH", None)
            if not service_account_path:
                service_account_path = os.environ.get("FCM_SERVICE_ACCOUNT_PATH", "")
            if service_account_path and not os.path.exists(service_account_path):
                service_account_path = ""

            enabled_setting = getattr(settings, "FCM_ENABLED", True)
            if isinstance(enabled_setting, str):
                enabled_setting = enabled_setting.strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }

            # Enable only when an API server key is explicitly configured.
            # Service-account auth may still be used for header generation when
            # available, but does not implicitly enable the service.
            has_credentials = bool(server_key)
            enabled = bool(enabled_setting and has_credentials)

            return FCMConfig(
                server_key=server_key, 
                project_id=project_id, 
                enabled=enabled,
                service_account_path=service_account_path or ""
            )
        except Exception as e:
            logger.warning(f"FCM configuration error: {e}")
            return FCMConfig(server_key="", project_id="", enabled=False)

    def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token using service account."""
        import json
        from datetime import UTC, datetime, timedelta

        # Check if we have a valid cached token
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._access_token

        if not self._config.service_account_path or not os.path.exists(self._config.service_account_path):
            return None

        try:
            # Read service account file
            with open(self._config.service_account_path, 'r') as f:
                service_account = json.load(f)

            # Create JWT token
            now = datetime.now(UTC)
            token_payload = {
                'iss': service_account['client_email'],
                'sub': service_account['client_email'],
                'aud': 'https://oauth2.googleapis.com/token',
                'iat': now,
                'exp': now + timedelta(hours=1),
                'scope': 'https://www.googleapis.com/auth/firebase.messaging'
            }

            # Create JWT header and payload
            import base64
            def b64encode_url(data):
                if isinstance(data, str):
                    data = data.encode('utf-8')
                return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

            header = {'alg': 'RS256', 'typ': 'JWT'}
            header_b64 = b64encode_url(json.dumps(header))
            payload_b64 = b64encode_url(json.dumps(token_payload))
            signing_input = f"{header_b64}.{payload_b64}"

            # Sign with private key
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend

            private_key = service_account['private_key'].encode('utf-8')
            private_key_obj = serialization.load_pem_private_key(
                private_key,
                password=None,
                backend=default_backend()
            )

            signature = private_key_obj.sign(
                signing_input.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            jwt_token = f"{signing_input}.{b64encode_url(signature)}"

            # Exchange JWT for access token
            token_response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': jwt_token
                },
                timeout=30
            )

            if token_response.status_code == 200:
                token_data = token_response.json()
                self._access_token = token_data.get('access_token')
                # Set expiry 5 minutes before actual expiry
                expires_in = token_data.get('expires_in', 3600)
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                return self._access_token
            else:
                logger.error(f"Failed to get access token: {token_response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for FCM request."""
        # Try to use service account authentication first
        access_token = self._get_access_token()
        if access_token:
            return {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        
        # Fallback to server key
        if self._config.server_key:
            return {
                "Authorization": f"key={self._config.server_key}",
                "Content-Type": "application/json",
            }
        
        return {"Content-Type": "application/json"}

    def send_to_token(
        self, token: str, notification: PushNotification, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Send notification to a single device token.

        Args:
            token: Device token from mobile app
            notification: PushNotification instance
            dry_run: If True, don't actually send (for testing)

        Returns:
            Dict with 'success', 'message_id', 'error' keys
        """
        if not self._config.enabled:
            return {"success": False, "error": "FCM is disabled"}

        if dry_run:
            logger.info(f"[DRY RUN] Would send to token: {token[:20]}...")
            return {"success": True, "message_id": "dry-run", "error": None}

        payload = {
            "to": token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "priority": notification.priority.value,
            "time_to_live": notification.time_to_live,
        }

        # Add optional fields
        if notification.icon:
            payload["notification"]["icon"] = notification.icon
        if notification.sound:
            payload["notification"]["sound"] = notification.sound
        if notification.badge is not None:
            payload["notification"]["badge"] = str(notification.badge)
        if notification.tag:
            payload["notification"]["tag"] = notification.tag
        if notification.color:
            payload["notification"]["color"] = notification.color
        if notification.click_action:
            payload["notification"]["click_action"] = notification.click_action
        if notification.data:
            payload["data"] = notification.data

        try:
            response = requests.post(
                self.FCM_URL, headers=self._get_headers(), json=payload, timeout=30
            )
            response.raise_for_status()

            result = response.json()

            if result.get("success", 0) > 0:
                message_id = result.get("message_id")
                logger.info(f"FCM notification sent successfully: {message_id}")
                return {"success": True, "message_id": message_id, "error": None}
            else:
                error = result.get("results", [{}])[0].get("error", "Unknown error")
                logger.error(f"FCM send failed: {error}")
                return {"success": False, "error": error}

        except requests.exceptions.RequestException as e:
            logger.error(f"FCM request failed: {e}")
            return {"success": False, "error": str(e)}

    def send_to_tokens(
        self, tokens: List[str], notification: PushNotification, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Send notification to multiple device tokens.

        Uses FCM batch sending for efficiency.

        Args:
            tokens: List of device tokens
            notification: PushNotification instance
            dry_run: If True, don't actually send

        Returns:
            Dict with success count, failure count, errors
        """
        if not self._config.enabled:
            return {"success": False, "error": "FCM is disabled"}

        if not tokens:
            return {"success": False, "error": "No tokens provided"}

        if dry_run:
            logger.info(f"[DRY RUN] Would send to {len(tokens)} tokens")
            return {"success": True, "sent": len(tokens), "failed": 0}

        # FCM supports up to 500 tokens per request
        results = {"success": 0, "failed": 0, "errors": []}

        # Process in batches of 500
        for i in range(0, len(tokens), 500):
            batch_tokens = tokens[i:i + 500]

            payload = {
                "registration_ids": batch_tokens,
                "notification": {
                    "title": notification.title,
                    "body": notification.body,
                },
                "priority": notification.priority.value,
                "time_to_live": notification.time_to_live,
            }

            # Add optional fields
            if notification.icon:
                payload["notification"]["icon"] = notification.icon
            if notification.sound:
                payload["notification"]["sound"] = notification.sound
            if notification.data:
                payload["data"] = notification.data

            try:
                response = requests.post(
                    self.FCM_URL, headers=self._get_headers(), json=payload, timeout=30
                )
                response.raise_for_status()
                result = response.json()

                # Count successes and failures
                if "results" in result:
                    for idx, item in enumerate(result["results"]):
                        if "error" in item:
                            results["failed"] += 1
                            results["errors"].append(
                                {
                                    "token": batch_tokens[idx][:20],
                                    "error": item["error"],
                                }
                            )
                        else:
                            results["success"] += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"FCM batch request failed: {e}")
                results["failed"] += len(batch_tokens)
                results["errors"].append({"error": str(e)})

        return results

    def send_to_topic(
        self, topic: str, notification: PushNotification, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Send notification to all devices subscribed to a topic.

        Args:
            topic: Topic name (e.g., 'announcements', 'resources')
            notification: PushNotification instance
            dry_run: If True, don't actually send
        """
        if not self._config.enabled:
            return {"success": False, "error": "FCM is disabled"}

        if dry_run:
            logger.info(f"[DRY RUN] Would send to topic: {topic}")
            return {"success": True, "message_id": "dry-run"}

        payload = {
            "to": f"/topics/{topic}",
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "priority": notification.priority.value,
            "time_to_live": notification.time_to_live,
        }

        if notification.data:
            payload["data"] = notification.data

        try:
            response = requests.post(
                self.FCM_URL, headers=self._get_headers(), json=payload, timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success", 0) > 0:
                return {"success": True, "message_id": result.get("message_id")}
            else:
                return {
                    "success": False,
                    "error": result.get("results", [{}])[0].get("error"),
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Subscribe devices to a topic.

        Args:
            tokens: List of device tokens
            topic: Topic name to subscribe to
        """
        if not self._config.enabled:
            return {"success": False, "error": "FCM is disabled"}

        # FCM Topic Subscription URL
        url = "https://iid.googleapis.com/iid/v1:batchAdd"

        payload = {"to": f"/topics/{topic}", "registration_tokens": tokens}

        headers = {
            "Authorization": f"key={self._config.server_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return {"success": True, "results": response.json()}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Unsubscribe devices from a topic.
        """
        if not self._config.enabled:
            return {"success": False, "error": "FCM is disabled"}

        url = "https://iid.googleapis.com/iid/v1:batchRemove"

        payload = {"to": f"/topics/{topic}", "registration_tokens": tokens}

        headers = {
            "Authorization": f"key={self._config.server_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return {"success": True, "results": response.json()}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}


# Singleton instance
fcm_service = FCMService()


# Convenience functions
def send_push_notification(
    token: str, title: str, body: str, **kwargs
) -> Dict[str, Any]:
    """Send a push notification to a single device."""
    notification = PushNotification(
        title=title,
        body=body,
        **{
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "icon",
                "sound",
                "badge",
                "tag",
                "color",
                "click_action",
                "data",
                "priority",
                "time_to_live",
            ]
        },
    )
    return fcm_service.send_to_token(token, notification)


def send_to_topic(topic: str, title: str, body: str, **kwargs) -> Dict[str, Any]:
    """Send a push notification to a topic."""
    notification = PushNotification(
        title=title,
        body=body,
        **{
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "icon",
                "sound",
                "badge",
                "tag",
                "color",
                "click_action",
                "data",
                "priority",
                "time_to_live",
            ]
        },
    )
    return fcm_service.send_to_topic(topic, notification)
