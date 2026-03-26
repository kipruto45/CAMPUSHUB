"""
SMS notification service for CampusHub.
Supports multiple SMS providers (Africa's Talking, generic HTTP).
"""

import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod

from django.conf import settings

logger = logging.getLogger(__name__)


class SMSProvider(ABC):
    """Base class for SMS providers."""

    @abstractmethod
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS to a phone number."""
        pass

    @abstractmethod
    def send_bulk_sms(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send SMS to multiple phone numbers."""
        pass


class AfricasTalkingSMSProvider(SMSProvider):
    """Africa's Talking SMS provider implementation."""

    def __init__(self):
        self.username = getattr(settings, "AFRICAS_TALKING_USERNAME", "")
        self.api_key = getattr(settings, "AFRICAS_TALKING_API_KEY", "")
        self.from_number = getattr(settings, "AFRICAS_TALKING_SHORT_CODE", "")

    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Africa's Talking."""
        if not self.username or not self.api_key:
            logger.warning("Africa's Talking not configured")
            return {"success": False, "error": "Africa's Talking not configured"}

        try:
            import requests

            url = f"https://api.africastalking.com/version1/messaging"
            headers = {
                "apiKey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            # Use form-encoded data as required by Africa's Talking API
            data = {
                "username": self.username,
                "message": message,
                "to": self._normalize_phone(to),
            }
            if str(self.from_number or "").strip():
                data["from"] = self.from_number

            logger.debug(f"Sending SMS to {to} via Africa's Talking")
            logger.debug(f"URL: {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Data: {data}")
            
            response = requests.post(url, data=data, headers=headers, timeout=30)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response text: {response.text}")
            
            # Check for HTTP errors first
            response.raise_for_status()
            result = response.json()

            if response.status_code == 200 and "SMSMessageData" in result:
                return {
                    "success": True,
                    "message_id": result["SMSMessageData"]["MessageId"],
                    "status": "Sent",
                }
            return {"success": False, "error": result.get("error", "Unknown error")}

        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                logger.error("Africa's Talking authentication failed. Please check your API key and username.")
                return {"success": False, "error": "Authentication failed. Please check your AFRICAS_TALKING_API_KEY and AFRICAS_TALKING_USERNAME settings."}
            logger.error(f"Africa's Talking HTTP error: {e}")
            return {"success": False, "error": f"HTTP error: {e}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Africa's Talking request failed: {e}")
            return {"success": False, "error": f"Request error: {e}"}
        except Exception as e:
            logger.error(f"Africa's Talking SMS failed: {e}")
            return {"success": False, "error": str(e)}

    def send_bulk_sms(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send bulk SMS via Africa's Talking."""
        try:
            import requests

            url = f"https://api.africastalking.com/version1/messaging"
            headers = {
                "apiKey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            # Africa's Talking bulk format uses recipients in the data dict
            data = {
                "username": self.username,
                "message": message,
                "bulkSMSMode": 1,
                "enqueue": 1,
                "recipients": ",".join([self._normalize_phone(to) for to in to_list]),
            }
            if str(self.from_number or "").strip():
                data["from"] = self.from_number

            response = requests.post(url, data=data, headers=headers)
            result = response.json()

            if response.status_code == 200:
                return {
                    "success": True,
                    "total": result.get("SMSMessageData", {}).get("Recipients", []),
                    "sent": len(to_list),
                }
            return {"success": False, "error": result.get("error", "Unknown error")}

        except Exception as e:
            logger.error(f"Africa's Talking bulk SMS failed: {e}")
            return {"success": False, "error": str(e)}

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            if len(phone) == 12 and phone.startswith("254"):
                phone = "+" + phone
            elif len(phone) == 10 and phone.startswith("0"):
                phone = "+254" + phone[1:]
        return phone


class GenericHTTPProvider(SMSProvider):
    """Generic HTTP/SMS gateway provider."""

    def __init__(self):
        self.api_url = getattr(settings, "SMS_API_URL", "")
        self.api_key = getattr(settings, "SMS_API_KEY", "")
        self.sender_id = getattr(settings, "SMS_SENDER_ID", "CampusHub")

    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via generic HTTP API."""
        if not self.api_url:
            logger.warning("SMS API not configured")
            return {"success": False, "error": "SMS API not configured"}

        try:
            import requests

            response = requests.post(
                self.api_url,
                json={
                    "to": to,
                    "message": message,
                    "from": self.sender_id,
                    "api_key": self.api_key,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "message_id": response.json().get("id", ""),
                    "status": "Sent",
                }
            return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Generic SMS failed: {e}")
            return {"success": False, "error": str(e)}

    def send_bulk_sms(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send bulk SMS via generic HTTP API."""
        return {"success": False, "error": "Bulk SMS not supported for generic provider"}


class SMSService:
    """Unified SMS service with provider selection."""

    PROVIDERS = {
        "africastalking": AfricasTalkingSMSProvider,
        "generic": GenericHTTPProvider,
    }

    def __init__(self):
        provider_name = str(
            getattr(settings, "SMS_PROVIDER", "africastalking")
            or "africastalking"
        )
        normalized_provider = provider_name.strip().lower().replace("_", "").replace("-", "")
        provider_class = self.PROVIDERS.get(
            normalized_provider,
            AfricasTalkingSMSProvider,
        )
        self.provider = provider_class()

    def send(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS to a single recipient."""
        return self.provider.send_sms(to, message)

    def send_bulk(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send SMS to multiple recipients."""
        return self.provider.send_bulk_sms(to_list, message)

    def send_payment_confirmation(
        self, phone: str, amount: str, currency: str, payment_type: str
    ) -> Dict[str, Any]:
        """Send payment confirmation SMS."""
        message = f"CampusHub: Payment of {currency} {amount} received for {payment_type}. Thank you!"
        return self.send(phone, message)

    def send_subscription_expiry_reminder(
        self, phone: str, days_remaining: int, plan_name: str
    ) -> Dict[str, Any]:
        """Send subscription expiry reminder."""
        message = f"CampusHub: Your {plan_name} subscription expires in {days_remaining} days. Renew now to continue premium features!"
        return self.send(phone, message)

    def send_payment_due_reminder(
        self, phone: str, amount: str, due_date: str
    ) -> Dict[str, Any]:
        """Send payment due reminder."""
        message = f"CampusHub: Payment of {amount} due on {due_date}. Please make your payment to avoid service interruption."
        return self.send(phone, message)


# Singleton instance
sms_service = SMSService()
