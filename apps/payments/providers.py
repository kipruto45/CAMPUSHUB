"""
Multi-payment provider integration for CampusHub.
Supports Stripe, PayPal, and mobile money (M-Pesa, etc.)
"""

import logging
import hashlib
import hmac
import uuid
from datetime import timedelta
from decimal import Decimal
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
        self.mode = getattr(settings, "PAYPAL_MODE", "sandbox")
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"

    def _get_access_token(self) -> Optional[str]:
        """Get PayPal access token."""
        import requests
        from requests.auth import HTTPBasicAuth

        try:
            response = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=HTTPBasicAuth(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return response.json().get("access_token")
        except Exception as e:
            logger.error(f"PayPal token获取失败: {e}")
            return None

    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Create PayPal order."""
        import requests

        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            response = requests.post(
                f"{self.base_url}/v2/checkout/orders",
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "reference_id": metadata.get("order_id", str(uuid.uuid4())),
                        "description": metadata.get("description", "CampusHub Payment"),
                        "amount": {
                            "currency_code": currency,
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
                }
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
            return {"success": False, "error": data.get("message", "Payment creation failed")}
        except Exception as e:
            logger.error(f"PayPal payment creation failed: {e}")
            return {"success": False, "error": str(e)}

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify PayPal payment status."""
        import requests

        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            response = requests.get(
                f"{self.base_url}/v2/checkout/orders/{payment_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            data = response.json()

            status = data.get("status", "").upper()
            purchase = data.get("purchase_units", [{}])[0]
            amount = purchase.get("payments", {}).get("captures", [{}])[0]

            return {
                "success": True,
                "status": "COMPLETED" if status == "COMPLETED" else "PENDING",
                "amount": Decimal(amount.get("value", "0")),
                "currency": amount.get("currency_code", "USD"),
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
        import requests

        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get PayPal access token"}

        try:
            # First capture the payment
            response = requests.post(
                f"{self.base_url}/v2/checkout/orders/{payment_id}/capture",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
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
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
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
        self.provider = getattr(settings, "MOBILE_MONEY_PROVIDER", "mpesa")
        self.short_code = getattr(settings, "MOBILE_MONEY_SHORT_CODE", "")
        self.consumer_key = getattr(settings, "MOBILE_MONEY_CONSUMER_KEY", "")
        self.consumer_secret = getattr(settings, "MOBILE_MONEY_CONSUMER_SECRET", "")
        self.env = getattr(settings, "MOBILE_MONEY_ENV", "sandbox")

    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> Dict[str, Any]:
        """Initiate mobile money payment (STK Push for M-Pesa)."""
        # This would integrate with M-Pesa API
        # For now, return payment reference
        payment_ref = f"MM-{uuid.uuid4().hex[:12].upper()}"
        
        return {
            "success": True,
            "provider": self.provider,
            "payment_id": payment_ref,
            "checkout_url": None,  # Mobile money doesn't use checkout URL
            "instructions": {
                "phone": metadata.get("phone_number"),
                "amount": str(amount),
                "reference": payment_ref,
                "message": f"Pay {amount} {currency} to {self.short_code}",
            }
        }

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """Verify mobile money payment status."""
        # In production, this would query the payment status from provider
        # For now, return placeholder
        return {
            "success": True,
            "status": "PENDING",
            "message": "Payment verification requires callback confirmation",
        }

    def process_webhook(self, payload: dict, signature: str) -> Dict[str, Any]:
        """Process mobile money callback."""
        # Verify signature
        if not self.consumer_secret or settings.DEBUG is True:
            return {
                "success": True,
                "event_type": "payment_received",
                "data": payload,
            }

        expected_signature = hmac.new(
            self.consumer_secret.encode(),
            str(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature and settings.DEBUG is not True:
            return {"success": False, "error": "Invalid signature"}
        
        return {
            "success": True,
            "event_type": "payment_received",
            "data": payload,
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

    def __init__(self):
        self.providers = {}
        for name, cls in self.PROVIDERS.items():
            try:
                self.providers[name] = cls()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(f"Failed to initialise provider {name}: {exc}")

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

        result = self.providers[provider].create_payment(
            amount, currency, provider_metadata
        )

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
    provider = service.providers["paypal"]
    
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
    service = PaymentService()
    provider = service.providers["mobile_money"]
    
    result = provider.process_webhook(payload, signature)
    
    if not result.get("success"):
        return result

    data = result.get("data", {})
    reference = data.get("MpesaReceiptNumber") or data.get("CheckoutRequestID") or data.get("MerchantRequestID") or data.get("reference") or data.get("payment_id")
    
    # Process successful payment
    if data.get("ResultCode") == 0:
        service.process_successful_payment(
            provider="mobile_money",
            provider_payment_id=reference,
            amount=Decimal(str(data.get("Amount", 0))),
            currency="KES"
        )

    return result


# ============== Singleton instance ==============

payment_service = PaymentService()
