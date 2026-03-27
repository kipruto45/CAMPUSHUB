"""
Stripe payment service for CampusHub.
Handles subscription management, payment processing, and webhooks.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from hashlib import sha256
from pathlib import Path
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import quote

try:
    import stripe
except ImportError:  # pragma: no cover - exercised in production fallback
    stripe = None

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


class StripeUnavailableError(RuntimeError):
    """Raised when Stripe SDK is required but unavailable."""


def _require_stripe_sdk() -> None:
    if stripe is None:
        raise StripeUnavailableError(
            "Stripe SDK is not installed. Add `stripe` to dependencies."
        )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding_needed = (-len(data)) % 4
    return base64.urlsafe_b64decode(f"{data}{'=' * padding_needed}")


def _parse_millis_timestamp(value: Any):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw) / 1000, tz=dt_timezone.utc)
        parsed = parse_datetime(raw)
        if parsed is not None:
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed, dt_timezone.utc)
            return parsed
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


class StripeService:
    """Service for Stripe payment operations."""

    def __init__(self):
        _require_stripe_sdk()
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
        self.webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    # ============== Customer Management ==============

    def create_customer(self, user) -> stripe.Customer:
        """Create a Stripe customer for a user."""
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip() or user.username,
            metadata={
                "user_id": str(user.id),
                "username": user.username,
            },
        )
        return customer

    def get_customer(self, customer_id: str) -> Optional[stripe.Customer]:
        """Retrieve a Stripe customer."""
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError:
            return None

    def get_or_create_customer(self, user):
        """Get existing customer or create new one."""
        from apps.payments.models import Subscription

        # Check for existing customer
        subscription = Subscription.objects.filter(
            user=user,
            stripe_customer_id__isnull=False,
        ).first()

        if subscription and subscription.stripe_customer_id:
            customer = self.get_customer(subscription.stripe_customer_id)
            if customer:
                return customer

        # Create new customer
        return self.create_customer(user)

    # ============== Subscription Management ==============

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: int = 0,
        metadata: dict = None
    ) -> stripe.Subscription:
        """Create a new subscription."""
        params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": metadata or {},
        }

        if trial_days > 0:
            params["trial_period_days"] = trial_days

        return stripe.Subscription.create(**params)

    def get_subscription(self, subscription_id: str) -> Optional[stripe.Subscription]:
        """Retrieve a subscription."""
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError:
            return None

    def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription."""
        subscription = self.get_subscription(subscription_id)
        if not subscription:
            return None

        if at_period_end:
            return stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        else:
            return stripe.Subscription.cancel(subscription_id)

    def reactivate_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Reactivate a canceled subscription."""
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )

    def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str
    ) -> stripe.Subscription:
        """Update subscription to a new price."""
        subscription = self.get_subscription(subscription_id)
        if not subscription:
            return None

        # Get the subscription item ID
        item_id = subscription["items"]["data"][0].id

        return stripe.Subscription.modify(
            subscription_id,
            items=[{
                "id": item_id,
                "price": new_price_id,
            }],
            proration_behavior="create_prorations"
        )

    # ============== Payment Methods ==============

    def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict = None
    ) -> stripe.checkout.Session:
        """Create a checkout session for subscription."""
        metadata = metadata or {}
        return stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            client_reference_id=metadata.get("local_subscription_id"),
            subscription_data={
                "metadata": metadata,
            },
        )

    def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a customer portal session for managing billing."""
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

    def get_payment_methods(self, customer_id: str) -> list:
        """Get customer's payment methods."""
        return stripe.PaymentMethod.list(
            customer=customer_id,
            type="card"
        )

    # ============== One-time Payments ==============

    def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "usd",
        customer_id: str = None,
        metadata: dict = None
    ) -> stripe.PaymentIntent:
        """Create a payment intent for one-time payment."""
        params = {
            "amount": int(amount * 100),  # Convert to cents
            "currency": currency,
            "metadata": metadata or {},
        }

        if customer_id:
            params["customer"] = customer_id

        return stripe.PaymentIntent.create(**params)

    # ============== Webhook Handling ==============

    def construct_webhook_event(self, payload: bytes, signature: str):
        """Construct and verify webhook event."""
        return stripe.Webhook.construct_event(
            payload,
            signature,
            self.webhook_secret
        )

    def handle_webhook(self, event: stripe.Event) -> dict:
        """Handle webhook event and return action info."""
        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "customer.created": self._handle_customer_created,
            "customer.updated": self._handle_customer_updated,
        }

        handler = handlers.get(event.type)
        if handler:
            return handler(event)
        else:
            logger.info(f"Unhandled webhook event: {event.type}")
            return {"action": "ignored", "event_type": event.type}

    def _handle_subscription_created(self, event: stripe.Event) -> dict:
        """Handle new subscription."""
        return {
            "action": "subscription_created",
            "subscription_id": event.data.object.id,
            "status": event.data.object.status,
            "customer_id": event.data.object.customer,
            "metadata": getattr(event.data.object, "metadata", {}) or {},
        }

    def _handle_subscription_updated(self, event: stripe.Event) -> dict:
        """Handle subscription update."""
        return {
            "action": "subscription_updated",
            "subscription_id": event.data.object.id,
            "status": event.data.object.status,
            "customer_id": event.data.object.customer,
            "metadata": getattr(event.data.object, "metadata", {}) or {},
        }

    def _handle_subscription_deleted(self, event: stripe.Event) -> dict:
        """Handle subscription cancellation."""
        return {
            "action": "subscription_deleted",
            "subscription_id": event.data.object.id,
        }

    def _handle_invoice_paid(self, event: stripe.Event) -> dict:
        """Handle successful invoice payment."""
        return {
            "action": "invoice_paid",
            "invoice_id": event.data.object.id,
            "amount_paid": event.data.object.amount_paid,
            "subscription_id": event.data.object.subscription,
            "customer_id": event.data.object.customer,
            "payment_intent_id": getattr(event.data.object, "payment_intent", None),
        }

    def _handle_invoice_payment_failed(self, event: stripe.Event) -> dict:
        """Handle failed invoice payment."""
        return {
            "action": "invoice_payment_failed",
            "invoice_id": event.data.object.id,
            "customer_id": event.data.object.customer,
        }

    def _handle_customer_created(self, event: stripe.Event) -> dict:
        """Handle new customer."""
        return {
            "action": "customer_created",
            "customer_id": event.data.object.id,
        }

    def _handle_customer_updated(self, event: stripe.Event) -> dict:
        """Handle customer update."""
        return {
            "action": "customer_updated",
            "customer_id": event.data.object.id,
        }


# ============== Helper Functions ==============

def get_stripe_service() -> StripeService:
    """Get Stripe service instance."""
    return StripeService()


def _stripe_value(stripe_object: Any, key: str, default=None):
    """Read values safely from Stripe objects or dict-like payloads."""
    if stripe_object is None:
        return default
    if isinstance(stripe_object, dict):
        return stripe_object.get(key, default)
    getter = getattr(stripe_object, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except TypeError:
            pass
    return getattr(stripe_object, key, default)


def sync_subscription_from_stripe(subscription_id: str) -> bool:
    """Sync local subscription with Stripe data."""
    from apps.payments.models import Plan, Subscription

    service = StripeService()
    stripe_sub = service.get_subscription(subscription_id)

    if not stripe_sub:
        return False

    try:
        metadata = _stripe_value(stripe_sub, "metadata", {}) or {}
        customer_id = _stripe_value(stripe_sub, "customer")

        local_sub = Subscription.objects.filter(
            stripe_subscription_id=subscription_id
        ).select_related("plan", "user").first()

        local_subscription_id = metadata.get("local_subscription_id")
        if not local_sub and local_subscription_id:
            local_sub = Subscription.objects.filter(
                pk=local_subscription_id
            ).select_related("plan", "user").first()

        if not local_sub and customer_id:
            local_sub = Subscription.objects.filter(
                stripe_customer_id=customer_id
            ).select_related("plan", "user").order_by("-created_at").first()

        price_id = None
        try:
            items = _stripe_value(stripe_sub, "items", {}) or {}
            data = _stripe_value(items, "data", []) or []
            first_item = data[0] if data else None
            price = _stripe_value(first_item, "price", {}) or {}
            price_id = _stripe_value(price, "id")
        except Exception:
            price_id = None

        plan = None
        if price_id:
            plan = Plan.objects.filter(
                stripe_monthly_price_id=price_id
            ).first() or Plan.objects.filter(
                stripe_yearly_price_id=price_id
            ).first()

        if not plan and metadata.get("plan_id"):
            plan = Plan.objects.filter(pk=metadata.get("plan_id")).first()

        if not local_sub and metadata.get("user_id") and plan:
            user = get_user_model().objects.filter(pk=metadata.get("user_id")).first()
            if user:
                local_sub = Subscription.objects.create(
                    user=user,
                    plan=plan,
                    stripe_customer_id=customer_id or "",
                    billing_period=metadata.get("billing_period", "monthly"),
                    status="unpaid",
                )

        if not local_sub:
            logger.error(
                "Local subscription not found for Stripe ID %s and no metadata fallback available",
                subscription_id,
            )
            return False

        if plan:
            local_sub.plan = plan

        # Update status and identifiers
        local_sub.stripe_subscription_id = subscription_id
        if customer_id:
            local_sub.stripe_customer_id = customer_id

        inferred_billing_period = metadata.get("billing_period")
        if not inferred_billing_period and plan and price_id:
            if price_id == plan.stripe_yearly_price_id:
                inferred_billing_period = "yearly"
            elif price_id == plan.stripe_monthly_price_id:
                inferred_billing_period = "monthly"
        if inferred_billing_period:
            local_sub.billing_period = inferred_billing_period

        local_sub.status = _stripe_value(stripe_sub, "status", local_sub.status)

        current_period_start = _stripe_value(stripe_sub, "current_period_start")
        current_period_end = _stripe_value(stripe_sub, "current_period_end")
        if current_period_start:
            local_sub.current_period_start = timezone.make_aware(
                timezone.datetime.fromtimestamp(current_period_start)
            )
        if current_period_end:
            local_sub.current_period_end = timezone.make_aware(
                timezone.datetime.fromtimestamp(current_period_end)
            )

        # Handle cancellation
        local_sub.cancel_at_period_end = bool(
            _stripe_value(stripe_sub, "cancel_at_period_end", False)
        )
        if local_sub.status == "canceled" and not local_sub.canceled_at:
            local_sub.canceled_at = timezone.now()

        local_sub.save()
        return True

    except Exception as exc:
        logger.error("Failed to sync subscription %s from Stripe: %s", subscription_id, exc)
        return False


def calculate_proration(
    subscription_id: str,
    new_price_id: str
) -> Decimal:
    """Calculate proration amount when switching plans."""
    service = StripeService()
    stripe_sub = service.get_subscription(subscription_id)

    if not stripe_sub:
        return Decimal("0.00")

    # Get proration invoice preview
    try:
        invoice = stripe.Invoice.retrieve(
            f"inprv_{subscription_id}",
            params={
                "subscription_details": {
                    "items": [{"id": stripe_sub["items"]["data"][0].id, "price": new_price_id}]
                }
            }
        )
        return Decimal(str(invoice.amount_due / 100))
    except Exception:
        return Decimal("0.00")


# ============== In-App Purchase Service ==============

class InAppPurchaseService:
    """Service for handling in-app purchases across platforms."""

    def __init__(self):
        self.stripe_service = get_stripe_service()

    # ============== Product Management ==============

    def get_available_products(self, platform: str = None, product_type: str = None):
        """Get available in-app products."""
        from apps.payments.models import InAppProduct

        queryset = InAppProduct.objects.filter(is_active=True, is_available=True)

        if platform:
            queryset = queryset.filter(platform=platform)
        if product_type:
            queryset = queryset.filter(product_type=product_type)

        return queryset.order_by("display_order", "name")

    def get_product_by_platform_id(self, platform: str, product_id: str):
        """Get product by platform-specific product ID."""
        from apps.payments.models import InAppProduct

        if platform == "apple":
            return InAppProduct.objects.filter(
                platform="apple",
                apple_product_id=product_id,
                is_active=True
            ).first()
        elif platform == "google":
            return InAppProduct.objects.filter(
                platform="google",
                google_product_id=product_id,
                is_active=True
            ).first()
        elif platform == "web":
            return InAppProduct.objects.filter(
                platform="web",
                stripe_price_id=product_id,
                is_active=True
            ).first()
        return None

    def get_products_for_tier(self, tier: str, platform: str = None):
        """Get products associated with a specific tier."""
        from apps.payments.models import InAppProduct

        queryset = InAppProduct.objects.filter(
            tier=tier,
            is_active=True,
            is_available=True
        )

        if platform:
            queryset = queryset.filter(platform=platform)

        return queryset.order_by("subscription_type", "price")

    # ============== Apple App Store (StoreKit 2) ==============

    def _calculate_period_end(self, product, validation: dict = None):
        validation = validation or {}
        expires_date = validation.get("expires_date")
        if expires_date:
            return expires_date

        period_start = validation.get("period_start") or timezone.now()
        if product.product_type != "subscription":
            return None
        if product.subscription_type == "monthly":
            return period_start + timedelta(days=30)
        if product.subscription_type == "yearly":
            return period_start + timedelta(days=365)
        return None

    def _parse_apple_receipt_fallback(self, receipt_data: str) -> dict:
        try:
            receipt_payload = json.loads(base64.b64decode(receipt_data))
        except Exception as exc:
            logger.error("Apple receipt validation failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "status": -1,
            }

        expires_date = _parse_millis_timestamp(
            receipt_payload.get("expires_date_ms")
            or receipt_payload.get("expiresDate")
        )

        return {
            "success": True,
            "receipt": receipt_payload,
            "status": 0,
            "validation_source": "fallback",
            "product_id": receipt_payload.get("product_id") or receipt_payload.get("productId"),
            "transaction_id": receipt_payload.get("transaction_id") or receipt_payload.get("transactionId"),
            "original_transaction_id": receipt_payload.get("original_transaction_id")
            or receipt_payload.get("originalTransactionId"),
            "expires_date": expires_date,
            "auto_renew_enabled": receipt_payload.get("auto_renew_status") not in {False, "false", "0", 0},
        }

    def _normalize_apple_validation(self, payload: dict, sandbox: bool) -> dict:
        latest_entry = None
        latest_receipt_info = payload.get("latest_receipt_info") or []
        in_app_items = payload.get("receipt", {}).get("in_app") or []
        candidates = latest_receipt_info or in_app_items
        if isinstance(candidates, list) and candidates:
            latest_entry = max(
                candidates,
                key=lambda entry: int(
                    str(
                        entry.get("expires_date_ms")
                        or entry.get("purchase_date_ms")
                        or "0"
                    )
                ),
            )

        expires_date = _parse_millis_timestamp(
            (latest_entry or {}).get("expires_date_ms")
            or (latest_entry or {}).get("expiresDate")
        )

        return {
            "success": True,
            "status": payload.get("status", 0),
            "receipt": payload,
            "validation_source": "apple_verify_receipt",
            "environment": "sandbox" if sandbox else "production",
            "product_id": (latest_entry or {}).get("product_id"),
            "transaction_id": (latest_entry or {}).get("transaction_id"),
            "original_transaction_id": (latest_entry or {}).get("original_transaction_id"),
            "expires_date": expires_date,
            "auto_renew_enabled": True,
            "raw_latest_receipt_info": latest_entry or {},
        }

    def _verify_apple_receipt(self, receipt_data: str, shared_secret: str) -> dict:
        endpoints = ["https://buy.itunes.apple.com/verifyReceipt"]
        if getattr(settings, "APPLE_IAP_USE_SANDBOX", False):
            endpoints = ["https://sandbox.itunes.apple.com/verifyReceipt"]

        payload = {
            "receipt-data": receipt_data,
        }
        if shared_secret:
            payload["password"] = shared_secret
        payload["exclude-old-transactions"] = True

        for index, endpoint in enumerate(endpoints):
            response = requests.post(
                endpoint,
                json=payload,
                timeout=getattr(settings, "APPLE_IAP_TIMEOUT_SECONDS", 30),
            )
            response.raise_for_status()
            data = response.json()

            # Apple returns 21007 when a sandbox receipt is sent to production.
            if data.get("status") == 21007 and "sandbox" not in endpoint:
                endpoints.append("https://sandbox.itunes.apple.com/verifyReceipt")
                continue
            if data.get("status") == 21008 and "sandbox" in endpoint and index == 0:
                endpoints.append("https://buy.itunes.apple.com/verifyReceipt")
                continue

            if data.get("status") != 0:
                return {
                    "success": False,
                    "status": data.get("status"),
                    "error": data.get("exception") or f"Apple receipt validation failed with status {data.get('status')}",
                    "receipt": data,
                }

            return self._normalize_apple_validation(data, sandbox="sandbox" in endpoint)

        return {
            "success": False,
            "status": -1,
            "error": "Apple receipt validation did not return a usable response",
        }

    def validate_apple_receipt(self, receipt_data: str, shared_secret: str = None) -> dict:
        """Validate Apple receipt with App Store.
        """
        effective_secret = str(
            shared_secret or getattr(settings, "APPLE_IAP_SHARED_SECRET", "") or ""
        ).strip()
        if effective_secret:
            try:
                return self._verify_apple_receipt(receipt_data, effective_secret)
            except requests.RequestException as exc:
                logger.warning(
                    "Apple verifyReceipt request failed, falling back to local receipt parsing: %s",
                    exc,
                )
        return self._parse_apple_receipt_fallback(receipt_data)

    def _load_google_service_account_info(self) -> dict:
        inline_json = str(getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "") or "").strip()
        inline_b64 = str(getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64", "") or "").strip()
        path_value = str(getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_PATH", "") or "").strip()

        raw_payload = ""
        if inline_json:
            raw_payload = inline_json
        elif inline_b64:
            raw_payload = base64.b64decode(inline_b64).decode("utf-8")
        elif path_value:
            raw_payload = Path(path_value).expanduser().read_text(encoding="utf-8")

        if not raw_payload:
            return {}

        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.exception("Invalid GOOGLE_PLAY service account JSON provided")
            return {}

    def _get_google_access_token(self) -> str:
        service_account = self._load_google_service_account_info()
        if not service_account:
            return ""

        client_email = str(service_account.get("client_email") or "").strip()
        private_key = str(service_account.get("private_key") or "").strip()
        token_uri = str(service_account.get("token_uri") or "https://oauth2.googleapis.com/token").strip()

        if not client_email or not private_key:
            return ""

        now = int(timezone.now().timestamp())
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": client_email,
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": token_uri,
            "iat": now,
            "exp": now + 3600,
        }
        signing_input = f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode())}.{_b64url_encode(json.dumps(claims, separators=(',', ':')).encode())}"

        private_key_obj = serialization.load_pem_private_key(
            private_key.encode("utf-8"),
            password=None,
        )
        signature = private_key_obj.sign(
            signing_input.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        assertion = f"{signing_input}.{_b64url_encode(signature)}"
        response = requests.post(
            token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=getattr(settings, "GOOGLE_PLAY_TIMEOUT_SECONDS", 30),
        )
        response.raise_for_status()
        return str(response.json().get("access_token") or "").strip()

    def process_apple_purchase(
        self,
        user,
        product_id: str,
        transaction_id: str,
        receipt_data: str = None
    ) -> dict:
        """Process Apple in-app purchase."""
        from apps.payments.models import InAppPurchase

        # Get product
        product = self.get_product_by_platform_id("apple", product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        validation = {}
        # Validate receipt
        if receipt_data:
            validation = self.validate_apple_receipt(receipt_data)
            if not validation.get("success"):
                return {"success": False, "error": validation.get("error") or "Invalid receipt"}

        resolved_transaction_id = str(
            validation.get("transaction_id") or transaction_id or ""
        ).strip()
        if not resolved_transaction_id:
            return {"success": False, "error": "Transaction id is required"}

        # Check for existing purchase
        existing = InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            apple_transaction_id=resolved_transaction_id
        ).first()

        if existing:
            return {"success": True, "purchase": existing, "already_processed": True}

        period_start = timezone.now()
        period_end = self._calculate_period_end(product, validation)
        original_transaction_id = str(
            validation.get("original_transaction_id") or resolved_transaction_id
        ).strip()

        # Create purchase record
        purchase = InAppPurchase.objects.create(
            user=user,
            product=product,
            platform="apple",
            apple_transaction_id=resolved_transaction_id,
            status="active",
            is_subscription=product.product_type == "subscription",
            subscription_type=product.subscription_type,
            period_start=period_start,
            period_end=period_end,
            expires_date=period_end,
            auto_renew_enabled=bool(validation.get("auto_renew_enabled", product.product_type == "subscription")),
            original_transaction_id=original_transaction_id,
            amount=product.price,
            currency=product.currency,
            metadata={
                "receipt_hash": sha256(receipt_data.encode("utf-8")).hexdigest() if receipt_data else None,
                "validation_source": validation.get("validation_source"),
                "environment": validation.get("environment"),
            }
        )

        # Handle feature unlock
        if product.product_type == "feature_unlock" and product.feature_key:
            self._unlock_feature(user, product, purchase)

        # Handle subscription tier upgrade
        if product.tier and product.product_type == "subscription":
            self._sync_subscription_from_iap(user, purchase, product)

        return {"success": True, "purchase": purchase}

    def handle_apple_subscription_renewal(
        self,
        user,
        original_transaction_id: str,
        new_transaction_id: str,
        expires_date: str
    ) -> dict:
        """Handle Apple subscription renewal."""
        from apps.payments.models import InAppPurchase

        # Find original purchase
        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            original_transaction_id=original_transaction_id
        ).first() or InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            apple_transaction_id=original_transaction_id
        ).first()

        if not purchase:
            return {"success": False, "error": "Original purchase not found"}

        # Update with new transaction
        purchase.apple_transaction_id = new_transaction_id
        parsed_expires_at = _parse_millis_timestamp(expires_date)
        purchase.period_end = parsed_expires_at
        purchase.expires_date = parsed_expires_at
        purchase.auto_renew_enabled = True
        purchase.status = "active"
        purchase.save(update_fields=["apple_transaction_id", "period_end", "expires_date", "auto_renew_enabled", "status", "updated_at"])

        return {"success": True, "purchase": purchase}

    def cancel_apple_subscription(
        self,
        user,
        transaction_id: str
    ) -> dict:
        """Cancel Apple subscription."""
        from apps.payments.models import InAppPurchase

        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            apple_transaction_id=transaction_id
        ).first()

        if not purchase:
            return {"success": False, "error": "Purchase not found"}

        purchase.auto_renew_enabled = False
        purchase.save(update_fields=["auto_renew_enabled", "updated_at"])

        return {"success": True, "purchase": purchase}

    # ============== Google Play Store (Billing Library) ==============

    def validate_google_purchase(
        self,
        product_id: str,
        purchase_token: str,
        package_name: str = None
    ) -> dict:
        """Validate Google Play purchase.
        """
        package_name = (
            str(package_name or "").strip()
            or str(getattr(settings, "GOOGLE_PLAY_PACKAGE_NAME", "") or "").strip()
        )
        product = self.get_product_by_platform_id("google", product_id)

        if not package_name:
            if getattr(settings, "GOOGLE_PLAY_STRICT_VALIDATION", False):
                return {"success": False, "error": "Google Play package name is not configured"}
            return {
                "success": True,
                "purchase_token": purchase_token,
                "acknowledged": True,
                "validation_source": "fallback",
            }

        access_token = ""
        try:
            access_token = self._get_google_access_token()
        except Exception as exc:
            logger.warning("Failed to fetch Google Play access token: %s", exc)

        if not access_token:
            if getattr(settings, "GOOGLE_PLAY_STRICT_VALIDATION", False):
                return {"success": False, "error": "Google Play service account is not configured"}
            return {
                "success": True,
                "purchase_token": purchase_token,
                "acknowledged": True,
                "validation_source": "fallback",
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        timeout = getattr(settings, "GOOGLE_PLAY_TIMEOUT_SECONDS", 30)

        try:
            if product and product.product_type == "subscription":
                url = (
                    "https://androidpublisher.googleapis.com/androidpublisher/v3/"
                    f"applications/{quote(package_name, safe='')}/purchases/subscriptionsv2/tokens/{quote(purchase_token, safe='')}"
                )
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                line_items = data.get("lineItems") or []
                latest_item = line_items[0] if line_items else {}
                expiry_time = _parse_millis_timestamp(
                    latest_item.get("expiryTime")
                    or latest_item.get("expiryTimeMillis")
                )
                subscription_state = str(data.get("subscriptionState") or "")
                return {
                    "success": True,
                    "purchase_token": purchase_token,
                    "acknowledged": data.get("acknowledgementState") in {"ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED", 1},
                    "expires_date": expiry_time,
                    "order_id": data.get("latestOrderId"),
                    "auto_renew_enabled": subscription_state not in {
                        "SUBSCRIPTION_STATE_CANCELED",
                        "SUBSCRIPTION_STATE_EXPIRED",
                        "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED",
                    },
                    "subscription_state": subscription_state,
                    "linked_purchase_token": data.get("linkedPurchaseToken"),
                    "raw": data,
                    "validation_source": "google_play_api",
                }

            url = (
                "https://androidpublisher.googleapis.com/androidpublisher/v3/"
                f"applications/{quote(package_name, safe='')}/purchases/products/{quote(product_id, safe='')}/tokens/{quote(purchase_token, safe='')}"
            )
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            purchase_state = int(data.get("purchaseState", 0) or 0)
            return {
                "success": purchase_state == 0,
                "purchase_token": purchase_token,
                "acknowledged": int(data.get("acknowledgementState", 0) or 0) == 1,
                "order_id": data.get("orderId"),
                "purchase_state": purchase_state,
                "consumption_state": int(data.get("consumptionState", 0) or 0),
                "raw": data,
                "validation_source": "google_play_api",
                "error": None if purchase_state == 0 else f"Google Play purchaseState={purchase_state}",
            }
        except requests.RequestException as exc:
            if getattr(settings, "GOOGLE_PLAY_STRICT_VALIDATION", False):
                return {"success": False, "error": str(exc)}
            logger.warning("Google Play validation failed, using fallback validation: %s", exc)
            return {
                "success": True,
                "purchase_token": purchase_token,
                "acknowledged": True,
                "validation_source": "fallback",
            }

    def process_google_purchase(
        self,
        user,
        product_id: str,
        purchase_token: str,
        order_id: str = None
    ) -> dict:
        """Process Google Play in-app purchase."""
        from apps.payments.models import InAppPurchase

        # Validate purchase
        validation = self.validate_google_purchase(product_id, purchase_token)
        if not validation.get("success"):
            return {"success": False, "error": validation.get("error") or "Invalid purchase"}

        # Get product
        product = self.get_product_by_platform_id("google", product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        # Check for existing purchase
        existing = InAppPurchase.objects.filter(
            user=user,
            platform="google",
            google_purchase_token=purchase_token
        ).first()

        if existing:
            return {"success": True, "purchase": existing, "already_processed": True}

        period_start = timezone.now()
        period_end = self._calculate_period_end(product, validation)
        resolved_order_id = str(validation.get("order_id") or order_id or "").strip()

        # Create purchase record
        purchase = InAppPurchase.objects.create(
            user=user,
            product=product,
            platform="google",
            google_purchase_token=purchase_token,
            status="active",
            is_subscription=product.product_type == "subscription",
            subscription_type=product.subscription_type,
            period_start=period_start,
            period_end=period_end,
            expires_date=period_end,
            auto_renew_enabled=bool(validation.get("auto_renew_enabled", product.product_type == "subscription")),
            amount=product.price,
            currency=product.currency,
            metadata={
                "order_id": resolved_order_id,
                "validation_source": validation.get("validation_source"),
                "acknowledged": validation.get("acknowledged"),
                "linked_purchase_token": validation.get("linked_purchase_token"),
            }
        )

        # Handle feature unlock
        if product.product_type == "feature_unlock" and product.feature_key:
            self._unlock_feature(user, product, purchase)

        # Handle subscription tier upgrade
        if product.tier and product.product_type == "subscription":
            self._sync_subscription_from_iap(user, purchase, product)

        return {"success": True, "purchase": purchase}

    def handle_google_subscription_renewal(
        self,
        user,
        purchase_token: str,
        expiry_time_millis: int
    ) -> dict:
        """Handle Google Play subscription renewal."""
        from apps.payments.models import InAppPurchase

        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="google",
            google_purchase_token=purchase_token
        ).first()

        if not purchase:
            return {"success": False, "error": "Purchase not found"}

        # Update expiry
        expires_at = _parse_millis_timestamp(expiry_time_millis)
        purchase.period_end = expires_at
        purchase.expires_date = expires_at
        purchase.auto_renew_enabled = True
        purchase.status = "active"
        purchase.save(update_fields=["period_end", "expires_date", "auto_renew_enabled", "status", "updated_at"])

        return {"success": True, "purchase": purchase}

    def cancel_google_subscription(
        self,
        user,
        purchase_token: str
    ) -> dict:
        """Cancel Google Play subscription."""
        from apps.payments.models import InAppPurchase

        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="google",
            google_purchase_token=purchase_token
        ).first()

        if not purchase:
            return {"success": False, "error": "Purchase not found"}

        purchase.auto_renew_enabled = False
        purchase.save(update_fields=["auto_renew_enabled", "updated_at"])

        return {"success": True, "purchase": purchase}

    # ============== Web (Stripe) ==============

    def create_web_checkout_session(
        self,
        user,
        product_id: str,
        success_url: str,
        cancel_url: str
    ) -> dict:
        """Create Stripe checkout session for web purchase."""
        from apps.payments.models import InAppProduct

        product = self.get_product_by_platform_id("web", product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        if not product.stripe_price_id:
            return {"success": False, "error": "Stripe price not configured"}

        # Get or create customer
        customer = self.stripe_service.get_or_create_customer(user)

        # Create checkout session
        checkout = self.stripe_service.create_checkout_session(
            customer_id=customer.id,
            price_id=product.stripe_price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "product_id": str(product.id),
                "platform": "web",
            }
        )

        return {
            "success": True,
            "checkout_url": checkout.url,
            "session_id": checkout.id,
        }

    def process_web_purchase(
        self,
        user,
        product_id: str,
        stripe_subscription_id: str
    ) -> dict:
        """Process web (Stripe) purchase from checkout."""
        from apps.payments.models import InAppProduct, InAppPurchase
        from django.utils import timezone

        product = self.get_product_by_platform_id("web", product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        # Get subscription from Stripe
        stripe_sub = self.stripe_service.get_subscription(stripe_subscription_id)
        if not stripe_sub:
            return {"success": False, "error": "Subscription not found"}

        # Calculate period
        period_start = timezone.make_aware(
            timezone.datetime.fromtimestamp(stripe_sub.current_period_start)
        )
        period_end = timezone.make_aware(
            timezone.datetime.fromtimestamp(stripe_sub.current_period_end)
        )

        # Create purchase record
        purchase = InAppPurchase.objects.create(
            user=user,
            product=product,
            platform="web",
            status="active",
            is_subscription=product.product_type == "subscription",
            subscription_type=product.subscription_type,
            period_start=period_start,
            period_end=period_end,
            expires_date=period_end,
            amount=product.price,
            currency=product.currency,
            metadata={
                "stripe_subscription_id": stripe_subscription_id,
            }
        )

        # Handle subscription tier upgrade
        if product.tier and product.product_type == "subscription":
            self._sync_subscription_from_iap(user, purchase, product)

        return {"success": True, "purchase": purchase}

    # ============== Restore Purchases ==============

    def restore_purchases(self, user, platform: str = None) -> dict:
        """Restore user's purchases for a platform."""
        from apps.payments.models import InAppPurchase

        purchases = InAppPurchase.objects.filter(
            user=user,
            status="active"
        )

        if platform:
            purchases = purchases.filter(platform=platform)

        # Check for expired subscriptions
        now = timezone.now()
        for purchase in purchases:
            if purchase.is_subscription and purchase.expires_date:
                if purchase.expires_date < now:
                    purchase.status = "expired"
                    purchase.save()

        restored = purchases.filter(status="active")

        return {
            "success": True,
            "purchases": [
                {
                    "id": str(p.id),
                    "product_name": p.product.name,
                    "platform": p.platform,
                    "is_subscription": p.is_subscription,
                    "expires_date": p.expires_date,
                }
                for p in restored
            ]
        }

    # ============== Cancel Subscription ==============

    def cancel_subscription(self, user, platform: str = None) -> dict:
        """Cancel user's subscription."""
        from apps.payments.models import InAppPurchase

        purchase = InAppPurchase.objects.filter(
            user=user,
            is_subscription=True,
            status="active"
        )

        if platform:
            purchase = purchase.filter(platform=platform)

        purchase = purchase.first()

        if not purchase:
            return {"success": False, "error": "No active subscription found"}

        # Mark as canceled (will expire at period end)
        purchase.auto_renew_enabled = False
        purchase.save()

        return {
            "success": True,
            "message": "Subscription will be canceled at period end",
            "expires_date": purchase.expires_date,
        }

    # ============== Helper Methods ==============

    def _unlock_feature(self, user, product, purchase):
        """Unlock a feature for the user."""
        from apps.payments.models import FeatureUnlock

        FeatureUnlock.objects.update_or_create(
            user=user,
            feature_key=product.feature_key,
            defaults={
                "feature_name": product.name,
                "purchase": purchase,
                "is_active": True,
                "expires_at": purchase.expires_date,
            }
        )

    def _sync_subscription_from_iap(self, user, purchase, product):
        """Sync in-app purchase to local subscription."""
        from apps.payments.models import Subscription, Plan

        plan = Plan.objects.filter(tier=product.tier, is_active=True).first()
        if not plan:
            return

        # Get or create subscription
        subscription = Subscription.objects.filter(
            user=user,
            status__in=["active", "trialing"]
        ).first()

        if subscription:
            # Update existing subscription
            subscription.plan = plan
            subscription.status = "active"
            subscription.current_period_start = purchase.period_start
            subscription.current_period_end = purchase.expires_date
            subscription.save()
        else:
            # Create new subscription
            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                status="active",
                billing_period=purchase.subscription_type or "monthly",
                current_period_start=purchase.period_start,
                current_period_end=purchase.expires_date,
            )

        # Link purchase to subscription
        purchase.subscription = subscription
        purchase.save(update_fields=["subscription", "updated_at"])

    def get_user_subscription(self, user) -> dict:
        """Get user's current subscription status."""
        from apps.payments.models import InAppPurchase

        # Get active subscription purchases
        active_sub = InAppPurchase.objects.filter(
            user=user,
            is_subscription=True,
            status="active"
        ).select_related("product").first()

        if not active_sub:
            return {
                "has_subscription": False,
                "subscription": None,
            }

        return {
            "has_subscription": True,
            "subscription": {
                "id": str(active_sub.id),
                "product_name": active_sub.product.name,
                "tier": active_sub.product.tier,
                "platform": active_sub.platform,
                "status": active_sub.status,
                "period_start": active_sub.period_start,
                "period_end": active_sub.expires_date,
                "auto_renew_enabled": active_sub.auto_renew_enabled,
            }
        }


def get_in_app_purchase_service() -> InAppPurchaseService:
    """Get in-app purchase service instance."""
    return InAppPurchaseService()
