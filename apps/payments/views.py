"""
Payment API views for CampusHub.
Provides endpoints for subscriptions, payments, and billing management.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Plan, Subscription, Payment, StorageUpgrade, PromoCode, InAppProduct, InAppPurchase
from .services import StripeService, get_stripe_service, sync_subscription_from_stripe, get_in_app_purchase_service
from .providers import payment_service

logger = logging.getLogger(__name__)


class PlanListView(APIView):
    """List available subscription plans."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List Plans",
        description="Get all available subscription plans"
    )
    def get(self, request, *args, **kwargs):
        plans = Plan.objects.filter(is_active=True).order_by("display_order")
        
        data = [{
            "id": str(plan.id),
            "name": plan.name,
            "tier": plan.tier,
            "description": plan.description,
            "price_monthly": str(plan.price_monthly),
            "price_yearly": str(plan.price_yearly),
            "billing_period": plan.billing_period,
            "storage_limit_gb": plan.storage_limit_gb,
            "max_upload_size_mb": plan.max_upload_size_mb,
            "download_limit_monthly": plan.download_limit_monthly,
            "can_download_unlimited": plan.can_download_unlimited,
            "has_ads": plan.has_ads,
            "has_priority_support": plan.has_priority_support,
            "has_analytics": plan.has_analytics,
            "has_early_access": plan.has_early_access,
            "is_featured": plan.is_featured,
            "stripe_monthly_price_id": plan.stripe_monthly_price_id,
            "stripe_yearly_price_id": plan.stripe_yearly_price_id,
        } for plan in plans]

        return Response({"plans": data})


class SubscriptionView(APIView):
    """Manage user subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Subscription",
        description="Get current user's subscription details"
    )
    def get(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(
            user=request.user,
            status__in=["active", "trialing", "past_due"]
        ).select_related("plan").first()

        if not subscription:
            return Response({
                "subscription": None,
                "plan": None
            })

        return Response({
            "subscription": {
                "id": str(subscription.id),
                "status": subscription.status,
                "billing_period": subscription.billing_period,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "trial_end": subscription.trial_end,
            },
            "plan": {
                "id": str(subscription.plan.id),
                "name": subscription.plan.name,
                "tier": subscription.plan.tier,
            }
        })

    @extend_schema(
        summary="Create Subscription",
        description="Create a new subscription with checkout"
    )
    def post(self, request, *args, **kwargs):
        plan_id = request.data.get("plan_id")
        billing_period = request.data.get("billing_period", "monthly")

        if not plan_id:
            return Response(
                {"error": "plan_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response(
                {"error": "Plan not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe = get_stripe_service()

        # Get or create customer
        customer = stripe.get_or_create_customer(request.user)

        # Keep a local subscription record so Stripe webhooks can reconcile back.
        local_subscription = Subscription.objects.filter(
            user=request.user,
            stripe_subscription_id="",
            status__in=["unpaid", "trialing", "past_due"],
        ).order_by("-created_at").first()

        if local_subscription:
            local_subscription.plan = plan
            local_subscription.stripe_customer_id = customer.id
            local_subscription.billing_period = billing_period
            local_subscription.status = "unpaid"
            local_subscription.save(
                update_fields=[
                    "plan",
                    "stripe_customer_id",
                    "billing_period",
                    "status",
                    "updated_at",
                ]
            )
        else:
            local_subscription = Subscription.objects.create(
                user=request.user,
                plan=plan,
                stripe_customer_id=customer.id,
                billing_period=billing_period,
                status="unpaid",
            )

        # Get price ID
        price_id = (
            plan.stripe_monthly_price_id if billing_period == "monthly"
            else plan.stripe_yearly_price_id
        )

        if not price_id:
            return Response(
                {"error": "Plan not available for purchase"},
                status=status.HTTP_400_BAD_REQUEST
        )

        # Create checkout session
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        try:
            checkout = stripe.create_checkout_session(
                customer_id=customer.id,
                price_id=price_id,
                success_url=f"{base_url}/settings/billing/success/",
                cancel_url=f"{base_url}/settings/billing/cancel/",
                metadata={
                    "user_id": str(request.user.id),
                    "plan_id": str(plan.id),
                    "billing_period": billing_period,
                    "local_subscription_id": str(local_subscription.id),
                },
            )
        except Exception as exc:
            logger.error(f"Stripe checkout session creation failed: {exc}")
            return Response(
                {"error": "Unable to start checkout. Please try again later."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_subscription.metadata = {
            **local_subscription.metadata,
            "checkout_session_id": checkout.id,
        }
        local_subscription.save(update_fields=["metadata", "updated_at"])

        return Response({
            "checkout_url": checkout.url,
            "session_id": checkout.id,
            "subscription_id": str(local_subscription.id),
        })


class SubscriptionCancelView(APIView):
    """Cancel subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cancel Subscription",
        description="Cancel subscription at period end"
    )
    def post(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(
            user=request.user,
            status__in=["active", "trialing"]
        ).first()

        if not subscription:
            return Response(
                {"error": "No active subscription found"},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe = get_stripe_service()
        if not subscription.stripe_subscription_id:
            return Response(
                {"error": "Subscription is not linked to a billing provider yet"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stripe.cancel_subscription(
                subscription.stripe_subscription_id,
                at_period_end=True
            )
        except Exception as exc:
            logger.error(f"Stripe cancellation failed: {exc}")
            return Response(
                {"error": "Unable to cancel subscription right now. Please try again later."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.cancel_at_period_end = True
        subscription.save()

        return Response({
            "message": "Subscription will be canceled at period end",
            "cancel_date": subscription.current_period_end,
        })


class SubscriptionReactivateView(APIView):
    """Reactivate canceled subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Reactivate Subscription",
        description="Reactivate a canceled subscription"
    )
    def post(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(
            user=request.user,
            status="active",
            cancel_at_period_end=True
        ).first()

        if not subscription:
            return Response(
                {"error": "No canceled subscription found"},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe = get_stripe_service()
        if not subscription.stripe_subscription_id:
            return Response(
                {"error": "Subscription is not linked to a billing provider yet"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stripe.reactivate_subscription(subscription.stripe_subscription_id)
        except Exception as exc:
            logger.error(f"Stripe reactivation failed: {exc}")
            return Response(
                {"error": "Unable to reactivate subscription right now. Please try again later."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.cancel_at_period_end = False
        subscription.save()

        return Response({"message": "Subscription reactivated"})


class BillingPortalView(APIView):
    """Billing management portal."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Billing Portal",
        description="Get billing portal URL for managing subscription"
    )
    def get(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(
            user=request.user,
            stripe_customer_id__isnull=False,
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            return Response(
                {"error": "No billing account found"},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe = get_stripe_service()
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        try:
            portal = stripe.create_portal_session(
                customer_id=subscription.stripe_customer_id,
                return_url=f"{base_url}/settings/billing/"
            )
        except Exception as exc:
            logger.error(f"Stripe portal session creation failed: {exc}")
            return Response(
                {"error": "Unable to open billing portal right now. Please try again later."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"portal_url": portal.url})


class PaymentHistoryView(APIView):
    """Payment history."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Payment History",
        description="Get user's payment history"
    )
    def get(self, request, *args, **kwargs):
        payments = Payment.objects.filter(
            user=request.user
        ).order_by("-created_at")[:50]

        data = [{
            "id": str(p.id),
            "amount": str(p.amount),
            "currency": p.currency,
            "status": p.status,
            "payment_type": p.payment_type,
            "created_at": p.created_at,
            "receipt_url": p.receipt_url or p.metadata.get("receipt_url", ""),
        } for p in payments]

        return Response({"payments": data})


class PaymentCreateView(APIView):
    """Create a payment with the requested provider (Stripe, PayPal, mobile money)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create Payment",
        description="Initiate a payment using Stripe, PayPal, or mobile money",
    )
    def post(self, request, *args, **kwargs):
        provider = request.data.get("provider", "stripe")
        amount = request.data.get("amount")
        currency = request.data.get("currency", "USD")
        description = request.data.get("description", "CampusHub payment")
        payment_type = request.data.get("payment_type", "one_time")

        if amount is None:
            return Response({"error": "amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_decimal = Decimal(str(amount))
        except Exception:
            return Response({"error": "amount must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        if amount_decimal <= 0:
            return Response({"error": "amount must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)

        metadata = request.data.get("metadata", {}) or {}
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        metadata.setdefault("success_url", f"{base_url}/settings/billing/success/")
        metadata.setdefault("cancel_url", f"{base_url}/settings/billing/cancel/")
        if request.data.get("phone_number"):
            metadata.setdefault("phone_number", request.data.get("phone_number"))

        result = payment_service.create_payment(
            provider=provider,
            amount=amount_decimal,
            currency=currency,
            description=description,
            user=request.user,
            payment_type=payment_type,
            **metadata,
        )

        if not result.get("success"):
            return Response({"error": result.get("error", "Payment creation failed")}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "provider": provider,
            "local_payment_id": result.get("local_payment_id"),
            "provider_payment_id": result.get("payment_id"),
            "checkout_url": result.get("checkout_url"),
            "instructions": result.get("instructions"),
            "client_secret": result.get("client_secret"),
        })


class PaymentStatusView(APIView):
    """Check payment status."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Payment Status",
        description="Verify payment status by provider or local payment id",
    )
    def get(self, request, *args, **kwargs):
        provider = request.query_params.get("provider")
        payment_id = request.query_params.get("payment_id")

        if not payment_id:
            return Response({"error": "payment_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Try local record first
        payment = Payment.objects.filter(id=payment_id).first()
        if payment:
            return Response({
                "status": payment.status,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "provider": payment.metadata.get("provider"),
                "provider_payment_id": payment.metadata.get("provider_payment_id") or payment.stripe_payment_intent_id,
                "receipt_url": payment.receipt_url or payment.metadata.get("receipt_url", ""),
                "metadata": payment.metadata,
            })

        if not provider:
            return Response({"error": "provider is required when payment is external"}, status=status.HTTP_400_BAD_REQUEST)

        result = payment_service.verify_payment(provider, payment_id)
        return Response(result)


class StorageUpgradeView(APIView):
    """Storage upgrade purchases."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Storage Upgrades",
        description="Get user's storage upgrades"
    )
    def get(self, request, *args, **kwargs):
        upgrades = StorageUpgrade.objects.filter(
            user=request.user
        ).order_by("-created_at")

        data = [{
            "id": str(u.id),
            "storage_gb": u.storage_gb,
            "duration_days": u.duration_days,
            "price": str(u.price),
            "status": u.status,
            "starts_at": u.starts_at,
            "ends_at": u.ends_at,
        } for u in upgrades]

        return Response({"upgrades": data})

    @extend_schema(
        summary="Purchase Storage Upgrade",
        description="Purchase additional storage"
    )
    def post(self, request, *args, **kwargs):
        storage_gb = int(request.data.get("storage_gb", 10))
        duration_days = int(request.data.get("duration_days", 30))
        provider = request.data.get("provider", "stripe")
        phone_number = request.data.get("phone_number")

        if storage_gb not in [5, 10, 20, 50, 100]:
            return Response(
                {"error": "Invalid storage amount"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate price (example: $2/GB/month)
        price_per_gb = Decimal("2.00")
        total_price = (price_per_gb * Decimal(storage_gb) * Decimal(duration_days)) / Decimal(30)

        # Create pending upgrade record
        upgrade = StorageUpgrade.objects.create(
            user=request.user,
            storage_gb=storage_gb,
            duration_days=duration_days,
            price=total_price,
            status="pending",
        )

        result = payment_service.create_payment(
            provider=provider,
            amount=total_price,
            currency="USD",
            description="Storage upgrade",
            user=request.user,
            payment_type="one_time",
            type="storage_upgrade",
            upgrade_id=str(upgrade.id),
            storage_gb=storage_gb,
            duration_days=duration_days,
            phone_number=phone_number,
        )

        if result.get("success"):
            upgrade.payment_id = result.get("local_payment_id")
            upgrade.save(update_fields=["payment", "updated_at"])
            return Response({
                "provider": provider,
                "upgrade_id": str(upgrade.id),
                "amount": str(total_price),
                "checkout_url": result.get("checkout_url"),
                "instructions": result.get("instructions"),
                "payment_id": result.get("local_payment_id"),
            })

        upgrade.status = "canceled"
        upgrade.save(update_fields=["status", "updated_at"])
        return Response({"error": result.get("error", "Payment creation failed")}, status=status.HTTP_400_BAD_REQUEST)


class ApplyPromoCodeView(APIView):
    """Apply promo code to subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Apply Promo Code",
        description="Apply a promotional code to get discount"
    )
    def post(self, request, *args, **kwargs):
        code = request.data.get("code", "").strip().upper()

        if not code:
            return Response(
                {"error": "Promo code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            promo = PromoCode.objects.get(code=code)
        except PromoCode.DoesNotExist:
            return Response(
                {"error": "Invalid promo code"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not promo.is_valid:
            return Response(
                {"error": "Promo code is expired or invalid"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user already used this code
        from apps.payments.models import UserCoupon
        usage_count = UserCoupon.objects.filter(
            user=request.user,
            promo_code=promo
        ).count()

        if usage_count >= promo.max_uses_per_user:
            return Response(
                {"error": "You have already used this promo code"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "code": promo.code,
            "discount_type": promo.discount_type,
            "discount_value": str(promo.discount_value),
            "description": promo.description,
        })


# ============== In-App Purchase Views ==============

class InAppProductListView(APIView):
    """List available in-app purchase products."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Products",
        description="Get available in-app purchase products"
    )
    def get(self, request, *args, **kwargs):
        platform = request.query_params.get("platform")
        product_type = request.query_params.get("type")

        service = get_in_app_purchase_service()
        products = service.get_available_products(platform=platform, product_type=product_type)

        data = [{
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "platform": p.platform,
            "product_type": p.product_type,
            "subscription_type": p.subscription_type,
            "price": str(p.price),
            "currency": p.currency,
            # Platform-specific purchase IDs (clients should send `platform_product_id` as `product_id`)
            "apple_product_id": p.apple_product_id,
            "google_product_id": p.google_product_id,
            "stripe_price_id": p.stripe_price_id,
            "platform_product_id": (
                p.apple_product_id
                if p.platform == "apple"
                else p.google_product_id
                if p.platform == "google"
                else p.stripe_price_id
                if p.platform == "web"
                else ""
            ),
            "tier": p.tier,
            "feature_key": p.feature_key,
            "is_available": p.is_available,
            "purchase_supported": bool(
                p.is_available
                and (
                    (p.platform == "apple" and p.apple_product_id)
                    or (p.platform == "google" and p.google_product_id)
                    or (p.platform == "web" and p.stripe_price_id and p.product_type == "subscription")
                )
            ),
        } for p in products]

        return Response({"products": data})


class InAppPurchaseSubscriptionView(APIView):
    """Get user's subscription status from in-app purchases."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Subscription",
        description="Get current user's subscription from in-app purchases"
    )
    def get(self, request, *args, **kwargs):
        service = get_in_app_purchase_service()
        result = service.get_user_subscription(request.user)
        return Response(result)


class InAppPurchaseSubscribeView(APIView):
    """Purchase subscription via in-app purchase."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Subscribe",
        description="Purchase a subscription via in-app purchase"
    )
    def post(self, request, *args, **kwargs):
        platform = request.data.get("platform")
        product_id = request.data.get("product_id")

        if not platform or not product_id:
            return Response(
                {"error": "platform and product_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = get_in_app_purchase_service()

        if platform == "apple":
            transaction_id = request.data.get("transaction_id")
            receipt_data = request.data.get("receipt_data")

            if not transaction_id:
                return Response(
                    {"error": "transaction_id is required for Apple purchases"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = service.process_apple_purchase(
                user=request.user,
                product_id=product_id,
                transaction_id=transaction_id,
                receipt_data=receipt_data
            )

        elif platform == "google":
            purchase_token = request.data.get("purchase_token")
            order_id = request.data.get("order_id")

            if not purchase_token:
                return Response(
                    {"error": "purchase_token is required for Google purchases"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = service.process_google_purchase(
                user=request.user,
                product_id=product_id,
                purchase_token=purchase_token,
                order_id=order_id
            )

        elif platform == "web":
            base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
            success_url = request.data.get("success_url", f"{base_url}/settings/billing/success/")
            cancel_url = request.data.get("cancel_url", f"{base_url}/settings/billing/cancel/")

            result = service.create_web_checkout_session(
                user=request.user,
                product_id=product_id,
                success_url=success_url,
                cancel_url=cancel_url
            )

        else:
            return Response(
                {"error": "Invalid platform. Use 'apple', 'google', or 'web'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not result.get("success"):
            return Response(
                {"error": result.get("error", "Purchase failed")},
                status=status.HTTP_400_BAD_REQUEST
            )

        if platform == "web":
            return Response({
                "checkout_url": result.get("checkout_url"),
                "session_id": result.get("session_id"),
            })

        return Response({
            "purchase_id": str(result.get("purchase").id) if result.get("purchase") else None,
            "already_processed": result.get("already_processed", False),
        })


class InAppPurchaseRestoreView(APIView):
    """Restore purchases for a user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Restore Purchases",
        description="Restore user's purchases"
    )
    def post(self, request, *args, **kwargs):
        platform = request.data.get("platform")  # Optional: restore for specific platform

        service = get_in_app_purchase_service()
        result = service.restore_purchases(request.user, platform=platform)

        return Response(result)


class InAppPurchaseCancelView(APIView):
    """Cancel user's subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cancel Subscription",
        description="Cancel user's subscription"
    )
    def post(self, request, *args, **kwargs):
        platform = request.data.get("platform")  # Optional: cancel for specific platform

        service = get_in_app_purchase_service()
        result = service.cancel_subscription(request.user, platform=platform)

        if not result.get("success"):
            return Response(
                {"error": result.get("error", "Cancel failed")},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result)


class FeatureUnlockListView(APIView):
    """List user's unlocked features."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Unlocked Features",
        description="Get user's unlocked features"
    )
    def get(self, request, *args, **kwargs):
        from apps.payments.models import FeatureUnlock

        features = FeatureUnlock.objects.filter(
            user=request.user,
            is_active=True
        )

        data = [{
            "id": str(f.id),
            "feature_key": f.feature_key,
            "feature_name": f.feature_name,
            "expires_at": f.expires_at,
        } for f in features]

        return Response({"features": data})


# ============== Webhook Handler ==============

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    signature = request.headers.get("stripe-signature")

    if not signature:
        return Response(
            {"error": "Missing stripe-signature header"},
            status=status.HTTP_400_BAD_REQUEST
        )

    stripe = get_stripe_service()

    try:
        event = stripe.construct_webhook_event(payload, signature)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return Response({"error": "Invalid webhook signature"}, status=status.HTTP_400_BAD_REQUEST)

    result = stripe.handle_webhook(event)

    action = result.get("action")
    if action == "subscription_created":
        _handle_subscription_created(result)
    elif action == "subscription_updated":
        _handle_subscription_updated(result)
    elif action == "subscription_deleted":
        _handle_subscription_deleted(result)
    elif action == "invoice_paid":
        _handle_invoice_paid(result)
    elif action == "invoice_payment_failed":
        _handle_invoice_payment_failed(result)

    return Response({"received": True})


def _handle_subscription_created(result):
    """Process new subscription."""
    _upsert_subscription_from_stripe(result.get("subscription_id"))


def _handle_subscription_updated(result):
    """Process subscription update."""
    sync_subscription_from_stripe(result.get("subscription_id"))


def _handle_subscription_deleted(result):
    """Process subscription deletion."""
    from apps.payments.models import Subscription

    subscription = Subscription.objects.filter(
        stripe_subscription_id=result.get("subscription_id")
    ).first()

    if subscription:
        subscription.status = "canceled"
        subscription.canceled_at = timezone.now()
        subscription.save()


def _handle_invoice_paid(result):
    """Process successful payment."""
    from apps.payments.models import Payment, Subscription

    invoice_id = result.get("invoice_id")
    provider_payment_id = result.get("payment_intent_id") or invoice_id
    payment = Payment.objects.filter(stripe_invoice_id=invoice_id).first()

    if payment:
        payment_service.process_successful_payment(
            provider="stripe",
            provider_payment_id=payment.stripe_payment_intent_id or provider_payment_id,
            amount=Decimal(str(result.get("amount_paid", 0))) / Decimal("100"),
            currency="USD",
        )
        return

    # If no local payment, try to link via subscription
    subscription_id = result.get("subscription_id")
    subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
    if subscription:
        payment = Payment.objects.create(
            user=subscription.user,
            subscription=subscription,
            payment_type="subscription",
            amount=Decimal(str(result.get("amount_paid", 0))) / Decimal("100"),
            currency="USD",
            stripe_invoice_id=invoice_id,
            stripe_payment_intent_id=provider_payment_id,
            status="pending",
            metadata={
                "provider": "stripe",
                "provider_payment_id": provider_payment_id,
            },
        )
        payment_service.process_successful_payment(
            provider="stripe",
            provider_payment_id=provider_payment_id,
            amount=payment.amount,
            currency=payment.currency,
        )


def _handle_invoice_payment_failed(result):
    """Process failed payment."""
    from apps.payments.models import Subscription, Payment
    from apps.notifications.models import Notification

    subscription = Subscription.objects.filter(
        stripe_customer_id=result.get("customer_id")
    ).first()

    if subscription:
        subscription.status = "past_due"
        subscription.save()

        # Notify user
        Notification.objects.create(
            recipient=subscription.user,
            title="Payment Failed",
            message="Your payment failed. Please update your payment method.",
            notification_type="payment",
            link="/settings/billing/",
        )

    invoice_id = result.get("invoice_id")
    payment = Payment.objects.filter(stripe_invoice_id=invoice_id).first()
    if payment:
        payment.status = "failed"
        payment.save()


def _upsert_subscription_from_stripe(stripe_subscription_id: str):
    """Create or update a subscription record from Stripe data."""
    if stripe_subscription_id:
        sync_subscription_from_stripe(stripe_subscription_id)


# ============== Helper Views ==============

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscription_limits(request, *args, **kwargs):
    """Get user's effective subscription limits."""
    from apps.payments.signals import get_user_plan_limits

    limits = get_user_plan_limits(request.user)
    return Response(limits)


# ============== Freemium Tier Views ==============

class TierListView(APIView):
    """List all available subscription tiers with their features."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get Tier Features",
        description="Get all available subscription tiers and their features"
    )
    def get(self, request, *args, **kwargs):
        from apps.payments.freemium import TIER_INFO, Tier

        tiers = []
        for tier in [Tier.FREE, Tier.PREMIUM, Tier.PRO, Tier.ENTERPRISE]:
            tier_info = TIER_INFO[tier]
            tiers.append(tier_info.to_dict())

        return Response({
            "tiers": tiers,
            "current_tier": None,  # Will be populated if authenticated
        })


class UserTierView(APIView):
    """Get current user's tier and feature access."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get User Tier",
        description="Get current user's subscription tier and features"
    )
    def get(self, request, *args, **kwargs):
        from apps.payments.freemium import (
            get_user_tier,
            get_user_tier_info,
            get_feature_access_summary,
            TIER_INFO,
        )

        user_tier = get_user_tier(request.user)
        tier_info = get_user_tier_info(request.user)
        access_summary = get_feature_access_summary(request.user)

        return Response({
            "tier": user_tier.value,
            "tier_name": tier_info.name if tier_info else "Free",
            "features": access_summary,
            "limits": {
                "storage_limit_gb": access_summary.get("storage_limit_gb"),
                "download_limit_monthly": access_summary.get("download_limit_monthly"),
            },
        })


class FeatureAccessView(APIView):
    """Check feature access for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Check Feature Access",
        description="Check if user has access to specific features"
    )
    def get(self, request, *args, **kwargs):
        from apps.payments.freemium import (
            Feature,
            has_feature,
            can_access_feature,
            get_feature_access_summary,
            FEATURE_METADATA,
        )

        # Get feature from query params
        feature_key = request.query_params.get("feature")

        if feature_key:
            # Check specific feature
            try:
                feature = Feature(feature_key)
            except ValueError:
                return Response(
                    {"error": f"Invalid feature: {feature_key}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            has_access, reason = can_access_feature(request.user, feature)
            return Response({
                "feature": feature_key,
                "has_access": has_access,
                "reason": reason,
                "feature_details": FEATURE_METADATA.get(feature),
            })

        # Return all features access summary
        access_summary = get_feature_access_summary(request.user)
        return Response(access_summary)


class TrialStartView(APIView):
    """Start a free trial for eligible users."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Start Trial",
        description="Start a free trial for Premium tier"
    )
    def post(self, request, *args, **kwargs):
        from apps.payments.freemium import (
            get_trial_eligibility,
            TRIAL_CONFIG,
            Tier,
        )
        from apps.payments.models import Subscription, Plan
        from django.utils import timezone
        from datetime import timedelta

        # Check eligibility
        eligibility = get_trial_eligibility(request.user)

        if not eligibility.get("eligible"):
            return Response(
                {"error": eligibility.get("reason", "Not eligible for trial")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create Premium plan
        try:
            plan = Plan.objects.get(tier="premium", is_active=True)
        except Plan.DoesNotExist:
            return Response(
                {"error": "Premium plan not available"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create trial subscription
        trial_end = timezone.now() + timedelta(days=TRIAL_CONFIG["duration_days"])

        subscription = Subscription.objects.create(
            user=request.user,
            plan=plan,
            status="trialing",
            current_period_start=timezone.now(),
            current_period_end=trial_end,
            trial_end=trial_end,
            metadata={"trial": True, "started_at": timezone.now().isoformat()},
        )

        return Response({
            "success": True,
            "tier": TRIAL_CONFIG["tier"].value,
            "duration_days": TRIAL_CONFIG["duration_days"],
            "trial_end": trial_end.isoformat(),
            "subscription_id": str(subscription.id),
        })
