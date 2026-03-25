"""
Payment webhook views for all providers.
"""

import logging
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import (handle_stripe_webhook, handle_paypal_webhook,
                         handle_mobile_money_webhook)

logger = logging.getLogger(__name__)


class StripeWebhookView(APIView):
    """Handle Stripe webhook events."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Stripe Webhook",
        description="Receive Stripe payment events"
    )
    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get("stripe-signature", "")
        
        result = handle_stripe_webhook(payload, signature)
        
        if result.get("success"):
            return Response({"received": True})
        
        return Response(
            {"error": result.get("error", "Webhook processing failed")},
            status=status.HTTP_400_BAD_REQUEST
        )


class PayPalWebhookView(APIView):
    """Handle PayPal webhook events."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="PayPal Webhook",
        description="Receive PayPal payment events"
    )
    def post(self, request, *args, **kwargs):
        payload = request.data
        signature = request.headers.get("paypal-transmission-sig", "")
        
        result = handle_paypal_webhook(payload, signature)
        
        if result.get("success"):
            return Response({"received": True})
        
        return Response(
            {"error": result.get("error", "Webhook processing failed")},
            status=status.HTTP_400_BAD_REQUEST
        )


class MobileMoneyWebhookView(APIView):
    """Handle mobile money webhook events (e.g., M-Pesa)."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Mobile Money Webhook",
        description="Receive mobile money payment callbacks"
    )
    def post(self, request, *args, **kwargs):
        payload = request.data
        signature = request.headers.get("x-signature", "")
        
        result = handle_mobile_money_webhook(payload, signature)
        
        if result.get("success"):
            return Response({"received": True})
        
        return Response(
            {"error": result.get("error", "Webhook processing failed")},
            status=status.HTTP_400_BAD_REQUEST
        )


class AppleWebhookView(APIView):
    """Handle Apple App Store server notifications."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Apple In-App Purchase Webhook",
        description="Receive Apple App Store server-to-server notifications",
    )
    def post(self, request, *args, **kwargs):
        logger.info("Received Apple in-app purchase webhook: %s", request.data)
        return Response({"received": True})


class GoogleWebhookView(APIView):
    """Handle Google Play billing notifications."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Google Play Billing Webhook",
        description="Receive Google Play billing notifications",
    )
    def post(self, request, *args, **kwargs):
        logger.info("Received Google Play billing webhook: %s", request.data)
        return Response({"received": True})


class PaymentWebhookSelectView(APIView):
    """Auto-detect and route webhook based on provider."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Payment Webhook Router",
        description="Auto-detect payment provider and process webhook"
    )
    def post(self, request, *args, **kwargs):
        # Try to detect provider from content
        content_type = request.headers.get("Content-Type", "")
        
        if "stripe" in content_type.lower() or "stripe-signature" in request.headers:
            return self._handle_stripe(request)
        elif "paypal" in content_type.lower():
            return self._handle_paypal(request)
        elif "mpesa" in str(request.data).lower() or "mobile" in content_type.lower():
            return self._handle_mobile_money(request)
        
        # Try to detect from payload
        if "stripe" in str(request.data).lower():
            return self._handle_stripe(request)
        
        return Response(
            {"error": "Unknown payment provider"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def _handle_stripe(self, request):
        payload = request.body
        signature = request.headers.get("stripe-signature", "")
        result = handle_stripe_webhook(payload, signature)
        return Response({"received": True}) if result.get("success") else Response({"error": "Failed"}, status=400)

    def _handle_paypal(self, request):
        result = handle_paypal_webhook(request.data, "")
        return Response({"received": True}) if result.get("success") else Response({"error": "Failed"}, status=400)

    def _handle_mobile_money(self, request):
        result = handle_mobile_money_webhook(request.data, "")
        return Response({"received": True}) if result.get("success") else Response({"error": "Failed"}, status=400)


# ============== In-App Purchase Webhooks ==============

class AppleWebhookView(APIView):
    """Handle Apple App Store webhook events (Server-to-Server Notifications)."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Apple Webhook",
        description="Receive Apple App Store server-to-server notifications"
    )
    def post(self, request, *args, **kwargs):
        from apps.payments.services import get_in_app_purchase_service
        from apps.payments.models import InAppPurchase
        from django.contrib.auth import get_user_model

        payload = request.data
        notification_type = payload.get("notificationType")
        transaction_id = payload.get("transactionId")
        original_transaction_id = payload.get("originalTransactionId")
        expires_date = payload.get("expiresDate")
        product_id = payload.get("productId")

        logger.info(f"Apple webhook received: {notification_type} for transaction {transaction_id}")

        service = get_in_app_purchase_service()

        try:
            if notification_type == "SUBSCRIBED":
                # New subscription
                product = service.get_product_by_platform_id("apple", product_id)
                if product:
                    # Find user from original transaction if available
                    purchase = InAppPurchase.objects.filter(
                        platform="apple",
                        apple_transaction_id=original_transaction_id
                    ).first()

                    if purchase:
                        user = purchase.user
                    else:
                        # For new subscriptions, we need user info from metadata
                        # This would typically come from a linked account
                        logger.warning(f"No user found for Apple transaction {transaction_id}")
                        return Response({"received": True})

                    result = service.process_apple_purchase(
                        user=user,
                        product_id=product_id,
                        transaction_id=transaction_id
                    )

            elif notification_type == "RENEWED" or notification_type == "INTERACTIVE_RENEWAL":
                # Subscription renewed
                purchase = InAppPurchase.objects.filter(
                    platform="apple",
                    apple_transaction_id=original_transaction_id
                ).first()

                if purchase:
                    service.handle_apple_subscription_renewal(
                        user=purchase.user,
                        original_transaction_id=original_transaction_id,
                        new_transaction_id=transaction_id,
                        expires_date=expires_date
                    )

            elif notification_type == "EXPIRED" or notification_type == "EXPIRED_SUBSCRIPTION":
                # Subscription expired
                purchase = InAppPurchase.objects.filter(
                    platform="apple",
                    apple_transaction_id=original_transaction_id
                ).first()

                if purchase:
                    purchase.status = "expired"
                    purchase.auto_renew_enabled = False
                    purchase.save()

            elif notification_type == "CANCELLED":
                # Subscription canceled
                purchase = InAppPurchase.objects.filter(
                    platform="apple",
                    apple_transaction_id=original_transaction_id
                ).first()

                if purchase:
                    service.cancel_apple_subscription(
                        user=purchase.user,
                        transaction_id=original_transaction_id
                    )

            elif notification_type == "REFUND" or notification_type == "REFUND_EXTENSION":
                # Refund processed
                purchase = InAppPurchase.objects.filter(
                    platform="apple",
                    apple_transaction_id=original_transaction_id
                ).first()

                if purchase:
                    purchase.status = "refunded"
                    purchase.save()

            return Response({"received": True})

        except Exception as e:
            logger.error(f"Apple webhook processing error: {e}")
            return Response(
                {"error": "Webhook processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GoogleWebhookView(APIView):
    """Handle Google Play Store webhook events (Real-time developer notifications)."""
    
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Google Webhook",
        description="Receive Google Play real-time developer notifications"
    )
    def post(self, request, *args, **kwargs):
        from apps.payments.services import get_in_app_purchase_service
        from apps.payments.models import InAppPurchase

        payload = request.data
        version = payload.get("version")
        notification_type = payload.get("notificationType")
        purchase_token = payload.get("purchaseToken")
        subscription_id = payload.get("subscriptionId")

        logger.info(f"Google webhook received: {notification_type} for token {purchase_token}")

        service = get_in_app_purchase_service()

        try:
            if notification_type == "SUBSCRIPTION_PURCHASED":
                # New subscription
                product = service.get_product_by_platform_id("google", subscription_id)
                if product:
                    purchase = InAppPurchase.objects.filter(
                        platform="google",
                        google_purchase_token=purchase_token
                    ).first()

                    if purchase:
                        user = purchase.user
                    else:
                        logger.warning(f"No user found for Google purchase token {purchase_token}")
                        return Response({"received": True})

                    result = service.process_google_purchase(
                        user=user,
                        product_id=subscription_id,
                        purchase_token=purchase_token
                    )

            elif notification_type == "SUBSCRIPTION_RENEWED":
                # Subscription renewed
                purchase = InAppPurchase.objects.filter(
                    platform="google",
                    google_purchase_token=purchase_token
                ).first()

                if purchase:
                    # Get expiry time from payload if available
                    expiry_time = payload.get("expiryTimeMillis", 0)
                    service.handle_google_subscription_renewal(
                        user=purchase.user,
                        purchase_token=purchase_token,
                        expiry_time_millis=int(expiry_time)
                    )

            elif notification_type == "SUBSCRIPTION_EXPIRED":
                # Subscription expired
                purchase = InAppPurchase.objects.filter(
                    platform="google",
                    google_purchase_token=purchase_token
                ).first()

                if purchase:
                    purchase.status = "expired"
                    purchase.auto_renew_enabled = False
                    purchase.save()

            elif notification_type == "SUBSCRIPTION_CANCELED":
                # Subscription canceled
                purchase = InAppPurchase.objects.filter(
                    platform="google",
                    google_purchase_token=purchase_token
                ).first()

                if purchase:
                    service.cancel_google_subscription(
                        user=purchase.user,
                        purchase_token=purchase_token
                    )

            elif notification_type == "SUBSCRIPTION_REVOKED":
                # Subscription revoked (refund)
                purchase = InAppPurchase.objects.filter(
                    platform="google",
                    google_purchase_token=purchase_token
                ).first()

                if purchase:
                    purchase.status = "refunded"
                    purchase.save()

            elif notification_type == "SUBSCRIPTION_PAUSED":
                # Subscription paused
                purchase = InAppPurchase.objects.filter(
                    platform="google",
                    google_purchase_token=purchase_token
                ).first()

                if purchase:
                    purchase.auto_renew_enabled = False
                    purchase.save()

            return Response({"received": True})

        except Exception as e:
            logger.error(f"Google webhook processing error: {e}")
            return Response(
                {"error": "Webhook processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
