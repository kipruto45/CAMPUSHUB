"""
SMS notification service for CampusHub.
Supports multiple SMS providers (Twilio, Africa's Talking, generic HTTP).
"""

import logging
from typing import Optional, Dict, Any, List
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


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS provider implementation."""

    def __init__(self):
        self.account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        self.auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        self.from_number = getattr(settings, "TWILIO_PHONE_NUMBER", "")

    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio."""
        if not self.account_sid or not self.auth_token:
            logger.warning("Twilio not configured")
            return {"success": False, "error": "Twilio not configured"}

        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(
                body=message,
                from_=self.from_number,
                to=self._normalize_phone(to)
            )
            return {
                "success": True,
                "message_id": msg.sid,
                "status": msg.status,
            }
        except Exception as e:
            logger.error(f"Twilio SMS failed: {e}")
            return {"success": False, "error": str(e)}

    def send_bulk_sms(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send bulk SMS via Twilio."""
        results = []
        for to in to_list:
            result = self.send_sms(to, message)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count > 0,
            "total": len(to_list),
            "sent": success_count,
            "failed": len(to_list) - success_count,
            "results": results,
        }

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            # Assume valid phone format, add + prefix
            if len(phone) == 12 and phone.startswith("254"):
                phone = "+" + phone
            elif len(phone) == 10 and phone.startswith("0"):
                phone = "+254" + phone[1:]
        return phone


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

            url = f"https://api.africas-talking.com/version1/messaging"
            headers = {
                "apiKey": self.api_key,
                "Content-Type": "application/json",
            }
            data = {
                "username": self.username,
                "message": message,
                "to": self._normalize_phone(to),
                "from": self.from_number,
            }

            response = requests.post(url, json=data, headers=headers)
            result = response.json()

            if response.status_code == 200 and "SMSMessageData" in result:
                return {
                    "success": True,
                    "message_id": result["SMSMessageData"]["MessageId"],
                    "status": "Sent",
                }
            return {"success": False, "error": result.get("error", "Unknown error")}

        except Exception as e:
            logger.error(f"Africa's Talking SMS failed: {e}")
            return {"success": False, "error": str(e)}

    def send_bulk_sms(self, to_list: List[str], message: str) -> Dict[str, Any]:
        """Send bulk SMS via Africa's Talking."""
        try:
            import requests

            url = f"https://api.africas-talking.com/version1/messaging"
            headers = {
                "apiKey": self.api_key,
                "Content-Type": "application/json",
            }
            data = {
                "username": self.username,
                "message": message,
                "bulkSMSMode": 1,
                "enqueue": 1,
                "recipients": [
                    {"phone": self._normalize_phone(to)} for to in to_list
                ],
            }

            response = requests.post(url, json=data, headers=headers)
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
        "twilio": TwilioSMSProvider,
        "africastalking": AfricasTalkingSMSProvider,
        "generic": GenericHTTPProvider,
    }

    def __init__(self):
        provider_name = getattr(settings, "SMS_PROVIDER", "twilio")
        provider_class = self.PROVIDERS.get(provider_name, TwilioSMSProvider)
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