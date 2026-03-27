"""
Payment webhook views for all providers.
"""

import base64
import json
import logging
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import (
    handle_mobile_money_webhook,
    handle_paypal_webhook,
    handle_stripe_webhook,
)

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
        if hasattr(request.data, "copy"):
            payload = request.data.copy()
        else:
            payload = dict(request.data)
        payload["_paypal_headers"] = {key.lower(): value for key, value in request.headers.items()}
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


def _b64url_decode(value: str) -> bytes:
    padding_needed = (-len(value)) % 4
    return base64.urlsafe_b64decode(f"{value}{'=' * padding_needed}")


def _decode_apple_signed_payload(payload: dict) -> dict:
    signed_payload = payload.get("signedPayload")
    if not signed_payload:
        return payload

    try:
        header_b64, body_b64, _sig = signed_payload.split(".")
        decoded = json.loads(_b64url_decode(body_b64))
        return decoded if isinstance(decoded, dict) else payload
    except Exception:
        logger.exception("Failed to decode Apple signedPayload")
        return payload


def _decode_google_rtdn_payload(payload: dict) -> dict:
    if not payload:
        return {}

    if "message" in payload and isinstance(payload.get("message"), dict):
        message = payload.get("message") or {}
        data = message.get("data")
        if isinstance(data, str):
            try:
                decoded = base64.b64decode(data).decode("utf-8")
                parsed = json.loads(decoded)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                logger.exception("Failed to decode Google RTDN message.data")

    return payload


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
        if hasattr(request.data, "copy"):
            payload = request.data.copy()
        else:
            payload = dict(request.data)
        payload["_paypal_headers"] = {key.lower(): value for key, value in request.headers.items()}
        result = handle_paypal_webhook(payload, "")
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

        raw_payload = request.data or {}
        payload = _decode_apple_signed_payload(raw_payload)

        notification_type = payload.get("notificationType") or payload.get("notification_type")
        transaction_id = payload.get("transactionId") or payload.get("transaction_id")
        original_transaction_id = payload.get("originalTransactionId") or payload.get("original_transaction_id")
        expires_date = payload.get("expiresDate") or payload.get("expires_date")
        product_id = payload.get("productId") or payload.get("product_id")

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

        raw_payload = request.data or {}
        payload = _decode_google_rtdn_payload(raw_payload)

        notification_type = payload.get("notificationType")
        purchase_token = payload.get("purchaseToken")
        subscription_id = payload.get("subscriptionId")

        if "subscriptionNotification" in payload:
            subscription_notification = payload.get("subscriptionNotification") or {}
            notification_type = subscription_notification.get("notificationType") or notification_type
            purchase_token = subscription_notification.get("purchaseToken") or purchase_token
            subscription_id = subscription_notification.get("subscriptionId") or subscription_id

        notification_type_map = {
            1: "SUBSCRIPTION_RECOVERED",
            2: "SUBSCRIPTION_RENEWED",
            3: "SUBSCRIPTION_CANCELED",
            4: "SUBSCRIPTION_PURCHASED",
            5: "SUBSCRIPTION_ON_HOLD",
            6: "SUBSCRIPTION_IN_GRACE_PERIOD",
            7: "SUBSCRIPTION_RESTARTED",
            8: "SUBSCRIPTION_PRICE_CHANGE_CONFIRMED",
            9: "SUBSCRIPTION_DEFERRED",
            10: "SUBSCRIPTION_PAUSED",
            11: "SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED",
            12: "SUBSCRIPTION_REVOKED",
            13: "SUBSCRIPTION_EXPIRED",
        }
        if isinstance(notification_type, int):
            notification_type = notification_type_map.get(notification_type, str(notification_type))
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
