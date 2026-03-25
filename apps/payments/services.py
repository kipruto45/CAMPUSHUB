"""
Stripe payment service for CampusHub.
Handles subscription management, payment processing, and webhooks.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

import stripe

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment operations."""

    def __init__(self):
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

    def validate_apple_receipt(self, receipt_data: str, shared_secret: str = None) -> dict:
        """Validate Apple receipt with App Store.
        
        Note: In production, use StoreKit 2 server APIs for validation.
        This is a simplified implementation.
        """
        import base64
        import json

        # In production, send receipt to Apple for validation
        # POST https://buy.itunes.apple.com/verifyReceipt
        # For subscriptions: POST https://buy.itunes.apple.com/verifyReceipt

        try:
            # Decode receipt (in production, send to Apple)
            receipt_payload = json.loads(base64.b64decode(receipt_data))

            return {
                "success": True,
                "receipt": receipt_payload,
                "status": 0,  # 0 = valid receipt
            }
        except Exception as e:
            logger.error(f"Apple receipt validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": -1,
            }

    def process_apple_purchase(
        self,
        user,
        product_id: str,
        transaction_id: str,
        receipt_data: str = None
    ) -> dict:
        """Process Apple in-app purchase."""
        from apps.payments.models import InAppProduct, InAppPurchase
        from django.utils import timezone

        # Get product
        product = self.get_product_by_platform_id("apple", product_id)
        if not product:
            return {"success": False, "error": "Product not found"}

        # Validate receipt
        if receipt_data:
            validation = self.validate_apple_receipt(receipt_data)
            if not validation.get("success"):
                return {"success": False, "error": "Invalid receipt"}

        # Check for existing purchase
        existing = InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            apple_transaction_id=transaction_id
        ).first()

        if existing:
            return {"success": True, "purchase": existing, "already_processed": True}

        # Calculate subscription period
        period_start = timezone.now()
        period_end = None

        if product.product_type == "subscription":
            if product.subscription_type == "monthly":
                from datetime import timedelta
                period_end = period_start + timedelta(days=30)
            elif product.subscription_type == "yearly":
                from datetime import timedelta
                period_end = period_start + timedelta(days=365)

        # Create purchase record
        purchase = InAppPurchase.objects.create(
            user=user,
            product=product,
            platform="apple",
            apple_transaction_id=transaction_id,
            status="active",
            is_subscription=product.product_type == "subscription",
            subscription_type=product.subscription_type,
            period_start=period_start,
            period_end=period_end,
            expires_date=period_end,
            amount=product.price,
            currency=product.currency,
            metadata={
                "receipt_data": receipt_data[:500] if receipt_data else None,
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
        from django.utils import timezone

        # Find original purchase
        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="apple",
            apple_transaction_id=original_transaction_id
        ).first()

        if not purchase:
            return {"success": False, "error": "Original purchase not found"}

        # Update with new transaction
        purchase.apple_transaction_id = new_transaction_id
        purchase.expires_date = timezone.parse(expires_date) if expires_date else None
        purchase.auto_renew_enabled = True
        purchase.save()

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
        purchase.save()

        return {"success": True, "purchase": purchase}

    # ============== Google Play Store (Billing Library) ==============

    def validate_google_purchase(
        self,
        product_id: str,
        purchase_token: str,
        package_name: str = None
    ) -> dict:
        """Validate Google Play purchase.
        
        Note: In production, use Google Play Developer API for validation.
        """
        # In production, use Google Play Developer API
        # POST https://androidpublisher.googleapis.com/androidpublisher/v3/
        # applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}

        return {
            "success": True,
            "purchase_token": purchase_token,
            "acknowledged": True,
        }

    def process_google_purchase(
        self,
        user,
        product_id: str,
        purchase_token: str,
        order_id: str = None
    ) -> dict:
        """Process Google Play in-app purchase."""
        from apps.payments.models import InAppProduct, InAppPurchase
        from django.utils import timezone

        # Validate purchase
        validation = self.validate_google_purchase(product_id, purchase_token)
        if not validation.get("success"):
            return {"success": False, "error": "Invalid purchase"}

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

        # Calculate subscription period
        period_start = timezone.now()
        period_end = None

        if product.product_type == "subscription":
            if product.subscription_type == "monthly":
                from datetime import timedelta
                period_end = period_start + timedelta(days=30)
            elif product.subscription_type == "yearly":
                from datetime import timedelta
                period_end = period_start + timedelta(days=365)

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
            amount=product.price,
            currency=product.currency,
            metadata={
                "order_id": order_id,
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
        from django.utils import timezone

        purchase = InAppPurchase.objects.filter(
            user=user,
            platform="google",
            google_purchase_token=purchase_token
        ).first()

        if not purchase:
            return {"success": False, "error": "Purchase not found"}

        # Update expiry
        purchase.expires_date = timezone.datetime.fromtimestamp(
            expiry_time_millis / 1000,
            tz=timezone.utc
        )
        purchase.auto_renew_enabled = True
        purchase.save()

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
        purchase.save()

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

        # Get or create subscription
        subscription = Subscription.objects.filter(
            user=user,
            status__in=["active", "trialing"]
        ).first()

        if subscription:
            # Update existing subscription
            plan = Plan.objects.filter(tier=product.tier, is_active=True).first()
            if plan:
                subscription.plan = plan
                subscription.status = "active"
                subscription.current_period_start = purchase.period_start
                subscription.current_period_end = purchase.expires_date
                subscription.save()
        else:
            # Create new subscription
            plan = Plan.objects.filter(tier=product.tier, is_active=True).first()
            if plan:
                Subscription.objects.create(
                    user=user,
                    plan=plan,
                    status="active",
                    billing_period=purchase.subscription_type or "monthly",
                    current_period_start=purchase.period_start,
                    current_period_end=purchase.expires_date,
                )

        # Link purchase to subscription
        purchase.subscription = subscription
        purchase.save()

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


# Initialize service
stripe_service = get_stripe_service()
iap_service = get_in_app_purchase_service()
