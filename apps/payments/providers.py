"""
Multi-payment provider integration for CampusHub.
Supports Stripe, PayPal, and mobile money (M-Pesa, etc.)
"""

import base64
import json
import logging
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============== Payment Provider Base Class ==============

class PaymentProvider(ABC):
    """Base class for payment providers."""

    @abstractmethod
    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Create a payment and return checkout URL or payment details."""
        pass

    @abstractmethod
    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify payment status."""
        pass

    @abstractmethod
    def process_webhook(self, payload: dict, signature: str) -> Dict[str, Any]:
        """Process webhook callback."""
        pass

    @abstractmethod
    def refund_payment(self, payment_id: str, amount: Decimal = None) -> Dict[str, Any]:
        """Refund a payment."""
        pass


# ============== Stripe Provider ==============

class StripePaymentProvider(PaymentProvider):
    """Stripe payment provider implementation."""

    def __init__(self):
        import stripe
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
        self.webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Create Stripe checkout session."""
        import stripe

        try:
            base_url = str(getattr(settings, "BASE_URL", "http://localhost:8000")).rstrip("/")
            success_url = metadata.get("success_url") or f"{base_url}/settings/billing/success/"
            cancel_url = metadata.get("cancel_url") or f"{base_url}/settings/billing/cancel/"
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": metadata.get("description", "CampusHub Payment"),
                        },
                        "unit_amount": int(amount * 100),  # Convert to cents
                    },
                    "quantity": 1,
                }],
                metadata=metadata,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return {
                "success": True,
                "provider": "stripe",
                "payment_id": session.id,
                "checkout_url": session.url,
                "client_secret": session.get("client_secret"),
            }
        except Exception as e:
            logger.error(f"Stripe payment creation failed: {e}")
            return {"success": False, "error": str(e)}

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify Stripe payment status."""
        import stripe

        try:
            session = stripe.checkout.Session.retrieve(payment_id)
            return {
                "success": True,
                "status": session.payment_status,
                "amount": session.amount_total / 100 if session.amount_total else 0,
                "currency": session.currency,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_webhook(self, payload: dict, signature: str) -> Dict[str, Any]:
        """Process Stripe webhook."""
        import stripe

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return {
                "success": True,
                "event_type": event.type,
                "data": event.data.object,
            }
        except Exception as e:
            logger.error(f"Stripe webhook verification failed: {e}")
            return {"success": False, "error": str(e)}

    def refund_payment(self, payment_id: str, amount: Decimal = None) -> Dict[str, Any]:
        """Refund Stripe payment."""
        import stripe

        try:
            params = {}
            if amount:
                params["amount"] = int(amount * 100)

            refund = stripe.Refund.create(payment_intent=payment_id, **params)
            return {
                "success": True,
                "refund_id": refund.id,
                "status": refund.status,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============== PayPal Provider ==============

class PayPalPaymentProvider(PaymentProvider):
    """PayPal payment provider implementation."""

    def __init__(self):
        self.client_id = getattr(settings, "PAYPAL_CLIENT_ID", "")
        self.client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
        self.mode = str(getattr(settings, "PAYPAL_MODE", "sandbox")).strip().lower()
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"
        self.request_timeout = int(getattr(settings, "PAYPAL_TIMEOUT_SECONDS", 30))

    def _get_access_token(self) -> Optional[str]:
        """Get PayPal access token."""
        if not self.client_id or not self.client_secret:
            logger.error("PayPal credentials are not configured")
            return None

        try:
            import requests
            from requests.auth import HTTPBasicAuth

            response = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=HTTPBasicAuth(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.request_timeout,
            )
            if not response.ok:
                logger.error("PayPal token request failed: %s", response.text)
                return None
            return (response.json() or {}).get("access_token")
        except Exception as e:
            logger.error(f"PayPal token request failed: {e}")
            return None

    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Create PayPal order."""
        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            import requests

            response = requests.post(
                f"{self.base_url}/v2/checkout/orders",
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "reference_id": metadata.get("order_id", str(uuid.uuid4())),
                        "description": metadata.get("description", "CampusHub Payment"),
                        "amount": {
                            "currency_code": str(currency).upper(),
                            "value": str(amount),
                        },
                    }],
                    "application_context": {
                        "return_url": metadata.get("success_url", "/settings/billing/success/"),
                        "cancel_url": metadata.get("cancel_url", "/settings/billing/cancel/"),
                    },
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.request_timeout,
            )
            data = response.json()

            if response.status_code == 201:
                # Find approval URL
                approval_url = next(
                    (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
                    None
                )
                return {
                    "success": True,
                    "provider": "paypal",
                    "payment_id": data["id"],
                    "checkout_url": approval_url,
                }
            return {
                "success": False,
                "error": data.get("message") or data.get("name") or "Payment creation failed",
            }
        except Exception as e:
            logger.error(f"PayPal payment creation failed: {e}")
            return {"success": False, "error": str(e)}

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify PayPal payment status."""
        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            import requests

            response = requests.get(
                f"{self.base_url}/v2/checkout/orders/{payment_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.request_timeout,
            )
            data = response.json()
            if not response.ok:
                return {
                    "success": False,
                    "error": data.get("message") or data.get("name") or "Failed to verify PayPal payment",
                }

            status = data.get("status", "").upper()
            purchase = (data.get("purchase_units") or [{}])[0]
            captures = ((purchase.get("payments") or {}).get("captures") or [])
            capture_amount = (captures[0].get("amount") if captures else None) or {}
            base_amount = purchase.get("amount", {}) or {}
            amount_data = capture_amount or base_amount

            return {
                "success": True,
                "status": "COMPLETED" if status == "COMPLETED" else "PENDING",
                "amount": Decimal(str(amount_data.get("value", "0"))),
                "currency": str(amount_data.get("currency_code", "USD")).upper(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_webhook(self, payload: dict, signature: str) -> Dict[str, Any]:
        """Process PayPal webhook."""
        # PayPal webhook verification would go here
        return {
            "success": True,
            "event_type": payload.get("event_type"),
            "data": payload.get("resource"),
        }

    def refund_payment(self, payment_id: str, amount: Decimal = None) -> Dict[str, Any]:
        """Refund PayPal payment."""
        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            import requests

            # First capture the payment
            response = requests.post(
                f"{self.base_url}/v2/checkout/orders/{payment_id}/capture",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=self.request_timeout,
            )
            
            if response.status_code == 201:
                capture_id = response.json()["purchase_units"][0]["payments"]["captures"][0]["id"]
                
                # Then refund if needed
                refund_data = {}
                if amount:
                    refund_data["amount"] = {"value": str(amount), "currency_code": "USD"}
                
                refund_response = requests.post(
                    f"{self.base_url}/v2/payments/captures/{capture_id}/refund",
                    json=refund_data if refund_data else None,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=self.request_timeout,
                )
                
                if refund_response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "refund_id": refund_response.json().get("id"),
                        "status": "COMPLETED",
                    }
            return {"success": False, "error": "Refund failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============== Mobile Money Provider ==============

class MobileMoneyProvider(PaymentProvider):
    """Mobile money provider (M-Pesa, etc.) implementation."""

    def __init__(self):
        self.provider = str(getattr(settings, "MOBILE_MONEY_PROVIDER", "mpesa")).strip().lower()
        self.short_code = getattr(settings, "MOBILE_MONEY_SHORT_CODE", "")
        self.consumer_key = getattr(settings, "MOBILE_MONEY_CONSUMER_KEY", "")
        self.consumer_secret = getattr(settings, "MOBILE_MONEY_CONSUMER_SECRET", "")
        self.passkey = getattr(settings, "MOBILE_MONEY_PASSKEY", "")
        self.env = str(getattr(settings, "MOBILE_MONEY_ENV", "sandbox")).strip().lower()
        self.transaction_type = str(
            getattr(settings, "MOBILE_MONEY_TRANSACTION_TYPE", "CustomerPayBillOnline")
        ).strip() or "CustomerPayBillOnline"
        self.request_timeout = int(getattr(settings, "MOBILE_MONEY_TIMEOUT_SECONDS", 30))
        self.base_url = str(getattr(settings, "BASE_URL", "http://localhost:8000")).strip().rstrip("/")
        configured_callback = str(getattr(settings, "MOBILE_MONEY_CALLBACK_URL", "")).strip()
        self.callback_url = configured_callback or f"{self.base_url}/api/payments/webhook/mobile-money/"
        configured_api_base = str(getattr(settings, "MOBILE_MONEY_API_BASE_URL", "")).strip().rstrip("/")
        if configured_api_base:
            self.api_base_url = configured_api_base
        else:
            self.api_base_url = (
                "https://sandbox.safaricom.co.ke"
                if self.env == "sandbox"
                else "https://api.safaricom.co.ke"
            )

    def _is_mpesa(self) -> bool:
        return self.provider in {"mpesa", "m-pesa"}

    def _normalize_phone_number(self, phone_number: str) -> Optional[str]:
        digits = "".join(ch for ch in str(phone_number or "") if ch.isdigit())
        if not digits:
            return None
        if digits.startswith("0") and len(digits) == 10:
            return f"254{digits[1:]}"
        if digits.startswith("254") and len(digits) == 12:
            return digits
        if digits.startswith("7") and len(digits) == 9:
            return f"254{digits}"
        return None

    def _get_access_token(self):
        try:
            import requests
            from requests.auth import HTTPBasicAuth
        except Exception as exc:
            return None, f"Requests dependency is missing: {exc}"

        try:
            response = requests.get(
                f"{self.api_base_url}/oauth/v1/generate?grant_type=client_credentials",
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                timeout=self.request_timeout,
            )
        except Exception as exc:
            return None, f"M-Pesa token request failed: {exc}"

        if not response.ok:
            return None, f"M-Pesa token request failed: {response.text}"

        token = (response.json() or {}).get("access_token")
        if not token:
            return None, "M-Pesa access token was not returned"
        return token, ""

    def _build_password(self, timestamp: str) -> str:
        raw = f"{self.short_code}{self.passkey}{timestamp}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    def _parse_callback(self, payload: dict) -> dict:
        body = (payload or {}).get("Body") or {}
        callback = body.get("stkCallback") or (payload or {}).get("stkCallback") or (payload or {})
        callback_metadata = (callback.get("CallbackMetadata") or {}).get("Item") or []

        metadata_map = {}
        for item in callback_metadata:
            key = item.get("Name")
            if key:
                metadata_map[key] = item.get("Value")

        result_code_raw = callback.get("ResultCode")
        try:
            result_code = int(result_code_raw)
        except Exception:
            result_code = result_code_raw

        normalized = {
            "MerchantRequestID": callback.get("MerchantRequestID") or payload.get("MerchantRequestID"),
            "CheckoutRequestID": callback.get("CheckoutRequestID") or payload.get("CheckoutRequestID"),
            "ResultCode": result_code,
            "ResultDesc": callback.get("ResultDesc") or payload.get("ResultDesc"),
            "Amount": metadata_map.get("Amount") or payload.get("Amount"),
            "MpesaReceiptNumber": metadata_map.get("MpesaReceiptNumber") or payload.get("MpesaReceiptNumber"),
            "PhoneNumber": metadata_map.get("PhoneNumber") or payload.get("PhoneNumber"),
            "TransactionDate": metadata_map.get("TransactionDate") or payload.get("TransactionDate"),
        }
        if metadata_map:
            normalized["CallbackMetadata"] = metadata_map
        normalized["reference"] = (
            normalized.get("CheckoutRequestID")
            or normalized.get("MerchantRequestID")
            or payload.get("payment_id")
            or payload.get("reference")
            or normalized.get("MpesaReceiptNumber")
        )
        return normalized

    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Initiate mobile money payment (STK Push for M-Pesa)."""
        if not self._is_mpesa():
            payment_ref = f"MM-{uuid.uuid4().hex[:12].upper()}"
            return {
                "success": True,
                "provider": self.provider,
                "payment_id": payment_ref,
                "checkout_url": None,
                "instructions": {
                    "phone": metadata.get("phone_number"),
                    "amount": str(amount),
                    "reference": payment_ref,
                    "message": f"Pay {amount} {currency} to {self.short_code}",
                },
            }

        if str(currency).upper() != "KES":
            return {"success": False, "error": "M-Pesa STK push requires currency KES"}

        phone_number = self._normalize_phone_number(metadata.get("phone_number"))
        if not phone_number:
            return {"success": False, "error": "Valid phone_number is required for M-Pesa STK push"}

        required = {
            "MOBILE_MONEY_SHORT_CODE": self.short_code,
            "MOBILE_MONEY_CONSUMER_KEY": self.consumer_key,
            "MOBILE_MONEY_CONSUMER_SECRET": self.consumer_secret,
            "MOBILE_MONEY_PASSKEY": self.passkey,
        }
        missing = [k for k, v in required.items() if not str(v or "").strip()]
        if missing:
            return {
                "success": False,
                "error": f"Missing mobile money configuration: {', '.join(missing)}",
            }

        token, token_error = self._get_access_token()
        if not token:
            return {"success": False, "error": token_error}

        try:
            import requests
        except Exception as exc:
            return {"success": False, "error": f"Requests dependency is missing: {exc}"}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._build_password(timestamp)
        amount_int = int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if amount_int <= 0:
            return {"success": False, "error": "amount must be greater than zero"}

        account_reference = (
            str(metadata.get("account_reference") or "").strip()
            or str(metadata.get("payment_id") or "").strip()
            or f"CH-{uuid.uuid4().hex[:8].upper()}"
        )[:20]

        transaction_desc = str(
            metadata.get("description") or "CampusHub payment"
        )[:180]

        payload = {
            "BusinessShortCode": self.short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.transaction_type,
            "Amount": amount_int,
            "PartyA": phone_number,
            "PartyB": self.short_code,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.request_timeout,
            )
        except Exception as exc:
            return {"success": False, "error": f"M-Pesa STK push request failed: {exc}"}

        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}

        if response.ok and str(data.get("ResponseCode")) == "0":
            checkout_request_id = (
                data.get("CheckoutRequestID")
                or data.get("MerchantRequestID")
                or str(metadata.get("payment_id") or "")
            )
            return {
                "success": True,
                "provider": "mpesa",
                "payment_id": checkout_request_id,
                "checkout_url": None,
                "instructions": {
                    "phone": phone_number,
                    "amount": str(amount_int),
                    "short_code": self.short_code,
                    "checkout_request_id": data.get("CheckoutRequestID"),
                    "merchant_request_id": data.get("MerchantRequestID"),
                    "customer_message": data.get("CustomerMessage"),
                },
                "raw_response": data,
            }

        return {
            "success": False,
            "error": (
                data.get("errorMessage")
                or data.get("ResponseDescription")
                or data.get("error")
                or "M-Pesa STK push failed"
            ),
            "raw_response": data,
        }

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify mobile money payment status."""
        if not self._is_mpesa():
            return {
                "success": True,
                "status": "PENDING",
                "message": "Payment verification requires callback confirmation",
            }

        if not payment_id:
            return {"success": False, "error": "payment_id is required"}

        required = [self.short_code, self.consumer_key, self.consumer_secret, self.passkey]
        if not all(str(v or "").strip() for v in required):
            return {"success": False, "error": "M-Pesa configuration is incomplete"}

        token, token_error = self._get_access_token()
        if not token:
            return {"success": False, "error": token_error}

        try:
            import requests
        except Exception as exc:
            return {"success": False, "error": f"Requests dependency is missing: {exc}"}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": self.short_code,
            "Password": self._build_password(timestamp),
            "Timestamp": timestamp,
            "CheckoutRequestID": payment_id,
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.request_timeout,
            )
        except Exception as exc:
            return {"success": False, "error": f"M-Pesa STK query failed: {exc}"}

        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}

        if not response.ok:
            return {"success": False, "error": data.get("errorMessage") or "M-Pesa STK query failed"}

        response_code = str(data.get("ResponseCode", ""))
        result_code_raw = data.get("ResultCode")
        try:
            result_code = int(result_code_raw)
        except Exception:
            result_code = None

        if response_code != "0":
            return {
                "success": False,
                "status": "FAILED",
                "message": data.get("ResponseDescription") or "M-Pesa STK query was rejected",
                "raw_response": data,
            }

        if result_code == 0:
            status_value = "COMPLETED"
        elif result_code in {1, 1032, 1037, 2001, 2025}:
            status_value = "FAILED"
        else:
            status_value = "PENDING"

        return {
            "success": True,
            "status": status_value,
            "result_code": result_code,
            "message": data.get("ResultDesc") or data.get("ResponseDescription"),
            "raw_response": data,
        }

    def process_webhook(self, payload: dict, signature: str) -> Dict[str, Any]:
        """Process mobile money callback."""
        payload = payload or {}
        normalized_payload = self._parse_callback(payload)

        if signature and self.consumer_secret and settings.DEBUG is not True:
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            expected_signature = hmac.new(
                self.consumer_secret.encode(),
                serialized,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return {"success": False, "error": "Invalid signature"}

        return {
            "success": True,
            "event_type": "payment_received",
            "data": normalized_payload,
        }

    def refund_payment(self, payment_id: str, amount: Decimal = None) -> Dict[str, Any]:
        """Refund mobile money payment (if supported)."""
        return {
            "success": False,
            "error": "Mobile money refunds not supported",
        }


# ============== Payment Service ==============

class PaymentService:
    """Service for handling all payment operations with multiple providers."""

    PROVIDERS = {
        "stripe": StripePaymentProvider,
        "paypal": PayPalPaymentProvider,
        "mobile_money": MobileMoneyProvider,
    }
    PROVIDER_ALIASES = {
        "mpesa": "mobile_money",
        "m-pesa": "mobile_money",
        "mobilemoney": "mobile_money",
        "mobile": "mobile_money",
    }

    def __init__(self):
        self.providers = {}
        for name, cls in self.PROVIDERS.items():
            try:
                self.providers[name] = cls()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(f"Failed to initialise provider {name}: {exc}")

    def _resolve_provider(self, provider: str) -> str:
        provider_key = str(provider or "").strip().lower()
        return self.PROVIDER_ALIASES.get(provider_key, provider_key)

    def create_payment(
        self,
        provider: str,
        amount: Decimal,
        currency: str = "USD",
        description: str = None,
        user=None,
        payment_type: str = "one_time",
        **metadata,
    ) -> Dict[str, Any]:
        """Create a payment with specified provider."""
        provider = self._resolve_provider(provider)
        if provider not in self.providers:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        from apps.payments.models import Payment

        with transaction.atomic():
            payment = Payment.objects.create(
                user=user,
                amount=amount,
                currency=currency,
                payment_type=payment_type,
                status="pending",
                metadata={
                    "provider": provider,
                    "description": description,
                    **metadata,
                },
            )

        provider_metadata = {
            "payment_id": str(payment.id),  # expose local id to provider for callbacks
            "description": description or "CampusHub payment",
            **metadata,
        }

        try:
            result = self.providers[provider].create_payment(
                amount, currency, provider_metadata
            )
        except Exception as exc:
            logger.error("Provider %s create_payment failed: %s", provider, exc)
            result = {"success": False, "error": str(exc)}

        if result.get("success"):
            provider_payment_id = result.get("payment_id")
            payment.stripe_payment_intent_id = provider_payment_id  # reuse field for non-Stripe too
            payment.metadata = {
                **payment.metadata,
                "provider_payment_id": provider_payment_id,
                "checkout_url": result.get("checkout_url"),
                "instructions": result.get("instructions"),
            }
            payment.save(update_fields=["stripe_payment_intent_id", "metadata", "updated_at"])
        else:
            payment.status = "failed"
            payment.metadata = {**payment.metadata, "error": result.get("error")}
            payment.save(update_fields=["status", "metadata", "updated_at"])

        # Return local payment id so clients can poll status without relying on provider identifiers
        result["local_payment_id"] = str(payment.id)
        return result

    def verify_payment(self, provider: str, payment_id: str) -> Dict[str, Any]:
        """Verify payment status."""
        provider = self._resolve_provider(provider)
        if provider not in self.providers:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        return self.providers[provider].verify_payment(payment_id)

    @transaction.atomic
    def process_successful_payment(
        self,
        provider: str,
        provider_payment_id: str,
        amount: Decimal,
        currency: str
    ) -> bool:
        """Process successful payment - update database and storage."""
        provider = self._resolve_provider(provider)
        from apps.payments.models import Payment, StorageUpgrade
        from apps.notifications.models import Notification
        from apps.payments.notifications import PaymentNotificationService

        try:
            # Find payment record
            payment = Payment.objects.filter(
                metadata__provider=provider,
                metadata__provider_payment_id=provider_payment_id
            ).first()

            if not payment:
                # Check by external ID
                payment = Payment.objects.filter(
                    stripe_payment_intent_id=provider_payment_id
                ).first()

            if not payment:
                logger.error(f"Payment not found for ID: {provider_payment_id}")
                return False

            # Check for duplicates (idempotency)
            if payment.status in ["succeeded", "partial"]:
                logger.info(f"Duplicate payment ignored: {provider_payment_id}")
                return True

            expected_amount = payment.amount or Decimal("0.00")
            paid_amount = Decimal(str(amount))

            payment.metadata = {
                **payment.metadata,
                "provider_payment_id": provider_payment_id,
                "paid_amount": str(paid_amount),
                "currency": currency,
            }
            # Attach signed receipt URL for downstream notifications/SMS
            try:
                from apps.payments.receipts import get_receipt_url_for_sms

                receipt_url = get_receipt_url_for_sms(payment)
                payment.metadata["receipt_url"] = receipt_url
                payment.receipt_url = receipt_url
            except Exception:
                pass

            if expected_amount > 0 and paid_amount < expected_amount:
                payment.status = "partial"
                payment.metadata["shortfall"] = str(expected_amount - paid_amount)
            else:
                payment.status = "succeeded"
                payment.amount = paid_amount
                payment.currency = currency

            payment.save(
                update_fields=[
                    "status",
                    "amount",
                    "currency",
                    "metadata",
                    "receipt_url",
                    "updated_at",
                ]
            )

            # Update subscription if applicable
            if payment.subscription and payment.status == "succeeded":
                subscription = payment.subscription
                subscription.status = "active"
                
                # Set period dates
                now = timezone.now()
                if subscription.billing_period == "monthly":
                    subscription.current_period_end = now + timedelta(days=30)
                else:
                    subscription.current_period_end = now + timedelta(days=365)
                subscription.current_period_start = now
                subscription.save()

                # Update user premium status
                user = payment.user
                user.is_premium = True
                if hasattr(subscription.plan, "tier"):
                    user.premium_plan = subscription.plan.tier
                user.save(update_fields=[f for f in ["is_premium", "premium_plan"] if hasattr(user, f)])

                # Notify subscription activation
                try:
                    PaymentNotificationService.send_subscription_activated_email(
                        user=user,
                        plan_name=getattr(subscription.plan, "name", "Subscription"),
                        billing_period=subscription.billing_period,
                        amount=paid_amount,
                        currency=currency,
                    )
                except Exception as notify_err:  # pragma: no cover
                    logger.error(f"Subscription activation notification error: {notify_err}")

            # Handle storage upgrade
            if payment.metadata.get("type") == "storage_upgrade" and payment.status == "succeeded":
                upgrade_id = payment.metadata.get("upgrade_id")
                upgrade_qs = StorageUpgrade.objects.filter(
                    user=payment.user,
                    status="pending"
                )
                if upgrade_id:
                    upgrade_qs = upgrade_qs.filter(id=upgrade_id)

                upgrade = upgrade_qs.first()
                if upgrade:
                    upgrade.status = "active"
                    upgrade.starts_at = timezone.now()
                    upgrade.ends_at = timezone.now() + timedelta(days=upgrade.duration_days)
                    upgrade.payment = payment
                    upgrade.save(update_fields=["status", "starts_at", "ends_at", "payment", "updated_at"])

                    # Update user's storage if the field exists
                    user = payment.user
                    if hasattr(user, "storage_limit_gb"):
                        user.storage_limit_gb = (user.storage_limit_gb or 0) + upgrade.storage_gb
                        user.save(update_fields=["storage_limit_gb"])

                    try:
                        PaymentNotificationService.send_storage_upgrade_confirmation_email(
                            user=user,
                            storage_gb=upgrade.storage_gb,
                            duration_days=upgrade.duration_days,
                            amount=paid_amount,
                            currency=currency,
                        )
                    except Exception as notify_err:  # pragma: no cover
                        logger.error(f"Storage upgrade notification error: {notify_err}")

            # Send notification
            Notification.objects.create(
                recipient=payment.user,
                title="Payment Successful",
                message=f"Your payment of {currency} {paid_amount} was successful.",
                notification_type="payment",
                link="/settings/billing/",
            )

            if payment.status == "succeeded":
                payment_type = payment.payment_type or payment.metadata.get("type", "payment")
                
                # Generate receipt URL for SMS
                receipt_url = None
                try:
                    from apps.payments.receipts import get_receipt_url_for_sms
                    receipt_url = get_receipt_url_for_sms(payment)
                except Exception:
                    pass
                
                try:
                    PaymentNotificationService.send_payment_success_email(
                        user=payment.user,
                        amount=paid_amount,
                        currency=currency,
                        payment_type=payment_type,
                        payment_id=str(payment.id),
                        payment=payment,  # For PDF attachment
                    )
                    PaymentNotificationService.send_payment_success_sms(
                        user=payment.user,
                        amount=str(paid_amount),
                        currency=currency,
                        payment_type=payment_type,
                        receipt_url=receipt_url,  # For SMS link
                    )
                except Exception as notify_err:  # pragma: no cover - best effort
                    logger.error(f"Payment notification error: {notify_err}")

            # Create activity log (best effort - should never fail payment success path)
            try:
                from apps.activity.models import RecentActivity

                RecentActivity.objects.create(
                    user=payment.user,
                    activity_type="payment",
                    description=f"Payment of {currency} {amount} completed",
                )
            except Exception as activity_err:  # pragma: no cover - defensive
                logger.error(f"RecentActivity logging failed: {activity_err}")

            logger.info(f"Payment processed successfully: {payment.id}")
            return True

        except Exception as e:
            logger.error(f"Payment processing failed: {e}")
            return False

    @transaction.atomic
    def process_failed_payment(
        self,
        provider: str,
        provider_payment_id: str,
        reason: str = None
    ) -> bool:
        """Process failed payment."""
        provider = self._resolve_provider(provider)
        from apps.payments.models import Payment, StorageUpgrade
        from apps.notifications.models import Notification
        from apps.payments.notifications import PaymentNotificationService

        payment = Payment.objects.filter(
            metadata__provider=provider,
            metadata__provider_payment_id=provider_payment_id
        ).first()

        if not payment:
            payment = Payment.objects.filter(
                stripe_payment_intent_id=provider_payment_id
            ).first()

        if not payment:
            return False

        payment.status = "failed"
        payment.metadata = {**payment.metadata, "failure_reason": reason}
        payment.save(update_fields=["status", "metadata", "updated_at"])

        # Cancel linked storage upgrade if pending
        if payment.metadata.get("type") == "storage_upgrade":
            upgrade_id = payment.metadata.get("upgrade_id")
            upgrade_qs = StorageUpgrade.objects.filter(user=payment.user, status="pending")
            if upgrade_id:
                upgrade_qs = upgrade_qs.filter(id=upgrade_id)
            upgrade_qs.update(status="canceled")

        # Notify user
        Notification.objects.create(
            recipient=payment.user,
            title="Payment Failed",
            message=f"Your payment failed. Reason: {reason or 'Unknown error'}",
            notification_type="payment",
            link="/settings/billing/payment-failed/",
        )
        try:
            PaymentNotificationService.send_payment_failure_email(
                user=payment.user,
                amount=payment.amount,
                currency=payment.currency,
                payment_type=payment.payment_type,
                reason=reason,
            )
        except Exception as notify_err:  # pragma: no cover
            logger.error(f"Payment failure notification error: {notify_err}")

        return True

    def refund_payment(
        self,
        provider: str,
        payment_id: str,
        amount: Decimal = None
    ) -> Dict[str, Any]:
        """Process refund."""
        provider = self._resolve_provider(provider)
        if provider not in self.providers:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        # Get payment record
        from apps.payments.models import Payment
        
        payment = Payment.objects.filter(id=payment_id).first()
        if not payment:
            return {"success": False, "error": "Payment not found"}

        # Process refund via provider
        result = self.providers[provider].refund_payment(
            payment.stripe_payment_intent_id or payment.metadata.get("provider_payment_id", ""),
            amount
        )

        if result.get("success"):
            # Update payment record
            payment.status = "refunded"
            if amount:
                payment.refunded_amount = amount
            payment.refunded_at = timezone.now()
            payment.save()

            try:
                from apps.payments.notifications import PaymentNotificationService

                PaymentNotificationService.send_refund_notification_email(
                    user=payment.user,
                    amount=amount or payment.amount,
                    currency=payment.currency,
                    payment_id=str(payment.id),
                    reason=result.get("reason"),
                )
            except Exception as notify_err:  # pragma: no cover
                logger.error(f"Refund notification error: {notify_err}")

        return result


# ============== Webhook Handlers ==============

def handle_stripe_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    from apps.payments.models import Payment, Subscription
    from apps.payments.services import StripeService, sync_subscription_from_stripe

    def _value(obj: Any, key: str, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        if hasattr(obj, key):
            return getattr(obj, key)
        getter = getattr(obj, "get", None)
        if callable(getter):
            try:
                return getter(key, default)
            except TypeError:
                pass
        return getattr(obj, key, default)

    service = PaymentService()
    stripe_service = StripeService()

    try:
        event = stripe_service.construct_webhook_event(payload, signature)
        action_result = stripe_service.handle_webhook(event) or {}
        event_type = _value(event, "type")
        data = _value(_value(event, "data"), "object", {})
        result = {
            "success": True,
            "event_type": event_type,
            "data": data,
            **action_result,
        }
    except Exception as exc:
        logger.error(f"Stripe webhook verification failed: {exc}")
        provider = service.providers["stripe"]
        result = provider.process_webhook(payload, signature)
        if not result.get("success"):
            return result
        event_type = result.get("event_type")
        data = result.get("data", {})

    if event_type == "checkout.session.completed":
        if _value(data, "mode") == "subscription":
            subscription_id = _value(data, "subscription")
            if subscription_id:
                sync_subscription_from_stripe(subscription_id)
        else:
            service.process_successful_payment(
                provider="stripe",
                provider_payment_id=_value(data, "id"),
                amount=Decimal(_value(data, "amount_total", 0) or 0) / Decimal("100"),
                currency=str(_value(data, "currency", "usd")).upper(),
            )
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        subscription_id = _value(data, "id")
        if subscription_id:
            sync_subscription_from_stripe(subscription_id)
    elif event_type == "customer.subscription.deleted":
        subscription_id = _value(data, "id")
        if subscription_id:
            subscription = Subscription.objects.filter(
                stripe_subscription_id=subscription_id
            ).first()
            if subscription:
                subscription.status = "canceled"
                subscription.canceled_at = timezone.now()
                subscription.cancel_at_period_end = False
                subscription.save(
                    update_fields=["status", "canceled_at", "cancel_at_period_end", "updated_at"]
                )
    elif event_type == "invoice.paid":
        subscription_id = _value(data, "subscription")
        if subscription_id:
            sync_subscription_from_stripe(subscription_id)

        provider_payment_id = _value(data, "payment_intent") or _value(data, "id")
        invoice_id = _value(data, "id")
        amount_paid = Decimal(_value(data, "amount_paid", 0) or 0) / Decimal("100")
        currency = str(_value(data, "currency", "usd")).upper()

        payment = Payment.objects.filter(stripe_invoice_id=invoice_id).first()
        if not payment and subscription_id:
            subscription = Subscription.objects.filter(
                stripe_subscription_id=subscription_id
            ).select_related("user", "plan").first()
            if subscription:
                payment = Payment.objects.create(
                    user=subscription.user,
                    subscription=subscription,
                    payment_type="subscription",
                    amount=amount_paid,
                    currency=currency,
                    stripe_invoice_id=invoice_id,
                    stripe_payment_intent_id=provider_payment_id or invoice_id,
                    status="pending",
                    description=f"{subscription.plan.name} subscription invoice",
                    metadata={
                        "provider": "stripe",
                        "provider_payment_id": provider_payment_id or invoice_id,
                    },
                )

        if provider_payment_id:
            service.process_successful_payment(
                provider="stripe",
                provider_payment_id=provider_payment_id,
                amount=amount_paid,
                currency=currency,
            )
    elif event_type == "payment_intent.payment_failed":
        service.process_failed_payment(
            provider="stripe",
            provider_payment_id=_value(data, "id"),
            reason=_value(_value(data, "last_payment_error", {}), "message"),
        )

    return result


def handle_paypal_webhook(payload: dict, signature: str) -> Dict[str, Any]:
    """Handle PayPal webhook events."""
    service = PaymentService()
    provider = service.providers.get("paypal")
    if not provider:
        return {"success": False, "error": "PayPal provider is unavailable"}
    
    result = provider.process_webhook(payload, signature)
    
    if not result.get("success"):
        return result

    event_type = result.get("event_type")
    
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        resource = result.get("data", {})
        service.process_successful_payment(
            provider="paypal",
            provider_payment_id=resource.get("id"),
            amount=Decimal(resource.get("amount", {}).get("value", 0)),
            currency=resource.get("amount", {}).get("currency_code", "USD")
        )

    return result


def handle_mobile_money_webhook(payload: dict, signature: str) -> Dict[str, Any]:
    """Handle mobile money webhook (e.g., M-Pesa callback)."""
    from apps.payments.models import Payment

    service = PaymentService()
    provider = service.providers.get("mobile_money")
    if not provider:
        return {"success": False, "error": "Mobile money provider is unavailable"}
    
    result = provider.process_webhook(payload, signature)
    
    if not result.get("success"):
        return result

    data = result.get("data", {}) or {}
    reference = (
        data.get("CheckoutRequestID")
        or data.get("MerchantRequestID")
        or data.get("reference")
        or data.get("payment_id")
        or data.get("MpesaReceiptNumber")
    )
    try:
        result_code = int(data.get("ResultCode"))
    except Exception:
        result_code = data.get("ResultCode")
    
    # Process successful payment
    if result_code == 0 and reference:
        service.process_successful_payment(
            provider="mobile_money",
            provider_payment_id=reference,
            amount=Decimal(str(data.get("Amount", 0))),
            currency="KES"
        )
        payment = Payment.objects.filter(
            metadata__provider="mobile_money",
            metadata__provider_payment_id=reference,
        ).first() or Payment.objects.filter(stripe_payment_intent_id=reference).first()
        if payment:
            payment.metadata = {
                **payment.metadata,
                "mpesa_receipt_number": data.get("MpesaReceiptNumber"),
                "mpesa_checkout_request_id": data.get("CheckoutRequestID"),
                "mpesa_merchant_request_id": data.get("MerchantRequestID"),
                "mpesa_phone_number": data.get("PhoneNumber"),
                "mpesa_result_desc": data.get("ResultDesc"),
            }
            payment.save(update_fields=["metadata", "updated_at"])
    elif result_code not in (None, "") and reference:
        service.process_failed_payment(
            provider="mobile_money",
            provider_payment_id=reference,
            reason=str(data.get("ResultDesc") or "Mobile money payment failed"),
        )

    return result


# ============== Singleton instance ==============

payment_service = PaymentService()
