"""
Tests for payment WebSocket and webhook functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from decimal import Decimal

from apps.payments.models import Plan, Subscription, Payment
from apps.payments.services import StripeService
from apps.payments.providers import PaymentService
from apps.payments.providers import handle_paypal_webhook


@pytest.fixture
def api_client():
    """Create an API client for payment endpoint tests."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def plan(db):
    """Create a test subscription plan."""
    return Plan.objects.create(
        name="Premium",
        tier="premium",
        price_monthly=9.99,
        price_yearly=99.99,
        stripe_monthly_price_id="price_premium_monthly",
        stripe_yearly_price_id="price_premium_yearly",
        storage_limit_gb=10,
        max_upload_size_mb=100,
        is_active=True,
    )


@pytest.mark.django_db
class TestPaymentWebhooks:
    """Tests for Stripe webhook handling."""

    @patch.object(StripeService, 'construct_webhook_event')
    @patch.object(StripeService, 'handle_webhook')
    @patch.object(StripeService, 'get_subscription')
    def test_webhook_subscription_created(self, mock_get_sub, mock_handle, mock_construct, api_client, user, plan):
        """Test handling subscription.created webhook."""
        # Mock Stripe event
        mock_event = MagicMock()
        mock_event.type = "customer.subscription.created"
        mock_event.data.object.id = "sub_123"
        mock_event.data.object.status = "active"
        mock_construct.return_value = mock_event
        mock_handle.return_value = {
            "action": "subscription_created",
            "subscription_id": "sub_123",
            "status": "active",
        }
        # Mock Stripe subscription fetch
        mock_stripe_sub = MagicMock()
        mock_stripe_sub.status = "active"
        mock_stripe_sub.current_period_start = 0
        mock_stripe_sub.current_period_end = 0
        mock_stripe_sub.cancel_at_period_end = False
        mock_stripe_sub.items = {"data": [{"price": {"id": plan.stripe_monthly_price_id}, "id": "si_1"}]}
        mock_get_sub.return_value = mock_stripe_sub

        # Create subscription record
        Subscription.objects.create(
            user=user,
            plan=plan,
            stripe_subscription_id="sub_123",
            status="trialing",
        )

        # Call webhook
        response = api_client.post(
            "/api/payments/webhook/",
            data=b'{"fake": "data"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature"
        )

        assert response.status_code == 200

    @patch.object(StripeService, 'construct_webhook_event')
    @patch.object(StripeService, 'handle_webhook')
    def test_webhook_invoice_paid(self, mock_handle, mock_construct, api_client, user, plan):
        """Test handling invoice.paid webhook."""
        mock_event = MagicMock()
        mock_event.type = "invoice.paid"
        mock_event.data.object.id = "in_123"
        mock_event.data.object.amount_paid = 999
        mock_construct.return_value = mock_event
        mock_handle.return_value = {
            "action": "invoice_paid",
            "invoice_id": "in_123",
            "amount_paid": 999,
            "subscription_id": "sub_123",
        }

        # Create subscription
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            stripe_subscription_id="sub_123",
            status="active",
        )

        # Create payment record
        Payment.objects.create(
            user=user,
            subscription=subscription,
            stripe_invoice_id="in_123",
            amount=9.99,
            status="pending",
        )

        response = api_client.post(
            "/api/payments/webhook/",
            data=b'{"fake": "data"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature"
        )

        assert response.status_code == 200

    @patch.object(StripeService, 'construct_webhook_event')
    @patch.object(StripeService, 'handle_webhook')
    def test_webhook_subscription_deleted(self, mock_handle, mock_construct, api_client, user, plan):
        """Test handling customer.subscription.deleted webhook."""
        mock_event = MagicMock()
        mock_event.type = "customer.subscription.deleted"
        mock_event.data.object.id = "sub_123"
        mock_construct.return_value = mock_event
        mock_handle.return_value = {
            "action": "subscription_deleted",
            "subscription_id": "sub_123",
        }

        # Create subscription
        Subscription.objects.create(
            user=user,
            plan=plan,
            stripe_subscription_id="sub_123",
            status="active",
        )

        response = api_client.post(
            "/api/payments/webhook/",
            data=b'{"fake": "data"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature"
        )

        # Verify subscription is canceled
        subscription = Subscription.objects.get(stripe_subscription_id="sub_123")
        assert subscription.status == "canceled"


@pytest.mark.django_db
class TestPaymentEndpoints:
    """Tests for payment REST endpoints."""

    def test_get_plans(self, api_client, user, plan):
        """Test GET /api/payments/plans/"""
        api_client.force_authenticate(user=user)
        
        response = api_client.get("/api/payments/plans/")
        
        assert response.status_code == 200
        assert "plans" in response.data
        assert len(response.data["plans"]) >= 1

    def test_get_subscription(self, api_client, user, plan):
        """Test GET /api/payments/subscription/"""
        api_client.force_authenticate(user=user)
        
        response = api_client.get("/api/payments/subscription/")
        
        assert response.status_code == 200

    def test_cancel_subscription(self, api_client, user, plan):
        """Test POST /api/payments/subscription/cancel/"""
        api_client.force_authenticate(user=user)
        
        # Create active subscription
        Subscription.objects.create(
            user=user,
            plan=plan,
            stripe_subscription_id="sub_123",
            status="active",
        )
        
        with patch("apps.payments.services.StripeService.cancel_subscription"):
            response = api_client.post("/api/payments/subscription/cancel/")
        
        assert response.status_code == 200

    def test_payment_history(self, api_client, user, plan):
        """Test GET /api/payments/payments/"""
        api_client.force_authenticate(user=user)
        
        # Create payment
        Payment.objects.create(
            user=user,
            amount=9.99,
            status="succeeded",
        )
        
        response = api_client.get("/api/payments/payments/")
        
        assert response.status_code == 200
        assert "payments" in response.data

    def test_get_subscription_limits(self, api_client, user):
        """Test GET /api/payments/limits/"""
        api_client.force_authenticate(user=user)
        
        response = api_client.get("/api/payments/limits/")
        
        assert response.status_code == 200
        assert "storage_gb" in response.data


@pytest.mark.django_db
def test_process_successful_payment_sets_receipt_url(user):
    service = PaymentService()
    service.providers["stripe"] = TestMultiProviderPayments()._stub_provider("STRIPE_TEST_001")
    result = service.create_payment(
        provider="stripe",
        amount=Decimal("4.00"),
        currency="USD",
        description="Stripe test",
        user=user,
    )
    provider_payment_id = result["payment_id"]

    service.process_successful_payment(
        provider="stripe",
        provider_payment_id=provider_payment_id,
        amount=Decimal("4.00"),
        currency="USD",
    )
    payment = Payment.objects.get(id=result["local_payment_id"])
    assert payment.metadata.get("receipt_url")


@pytest.mark.django_db
class TestMultiProviderPayments:
    """Ensure multi-provider payment service behaves correctly."""

    def _stub_provider(self, payment_id="TESTPAY"):
        class Stub:
            def create_payment(self, amount, currency, metadata):
                return {
                    "success": True,
                    "payment_id": payment_id,
                    "checkout_url": "http://example.com/checkout",
                    "instructions": {"note": "stub"},
                }

            def verify_payment(self, payment_id):
                return {"success": True, "status": "COMPLETED"}

            def process_webhook(self, payload, signature):
                return {"success": True, "event_type": "COMPLETED", "data": {}}

            def refund_payment(self, payment_id, amount=None):
                return {"success": True}

        return Stub()

    def test_create_payment_records_metadata(self, db, user):
        service = PaymentService()
        service.providers["paypal"] = self._stub_provider("PAYPAL123")

        result = service.create_payment(
            provider="paypal",
            amount=Decimal("10.00"),
            currency="USD",
            description="Test PayPal payment",
            user=user,
            payment_type="one_time",
        )

        assert result["success"] is True
        assert result.get("local_payment_id")

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.metadata.get("provider") == "paypal"
        assert payment.metadata.get("provider_payment_id") == "PAYPAL123"
        assert payment.stripe_payment_intent_id == "PAYPAL123"

    def test_partial_payment_marks_partial(self, db, user):
        service = PaymentService()
        service.providers["mobile_money"] = self._stub_provider("MM123")

        result = service.create_payment(
            provider="mobile_money",
            amount=Decimal("20.00"),
            currency="USD",
            description="Mobile money",
            user=user,
            payment_type="one_time",
        )

        service.process_successful_payment(
            provider="mobile_money",
            provider_payment_id="MM123",
            amount=Decimal("10.00"),  # half paid
            currency="USD",
        )

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status == "partial"
        assert payment.metadata.get("shortfall") == "10.00"

    def test_duplicate_success_is_idempotent(self, db, user):
        service = PaymentService()
        service.providers["paypal"] = self._stub_provider("PAYPAL321")

        result = service.create_payment(
            provider="paypal",
            amount=Decimal("5.00"),
            currency="USD",
            description="Dup check",
            user=user,
            payment_type="one_time",
        )

        assert service.process_successful_payment("paypal", "PAYPAL321", Decimal("5.00"), "USD") is True
        # second call should be ignored but still return True
        assert service.process_successful_payment("paypal", "PAYPAL321", Decimal("5.00"), "USD") is True

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status == "succeeded"

    def test_mobile_money_webhook_success(self, db, user):
        service = PaymentService()
        service.providers["mobile_money"] = self._stub_provider("MM999")

        result = service.create_payment(
            provider="mobile_money",
            amount=Decimal("3.00"),
            currency="USD",
            description="MM test",
            user=user,
            payment_type="one_time",
        )

        # simulate webhook
        from apps.payments.providers import handle_mobile_money_webhook

        payload = {"ResultCode": 0, "MpesaReceiptNumber": "MM999", "Amount": 3}
        response = handle_mobile_money_webhook(payload, "testsig")
        assert response.get("success") is True

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status in ["succeeded", "partial"]

    def test_paypal_webhook_success(self, db, user):
        service = PaymentService()

        # Create payment record via provider
        service.providers["paypal"] = self._stub_provider("PAYPAL777")
        result = service.create_payment(
            provider="paypal",
            amount=Decimal("12.00"),
            currency="USD",
            description="PayPal test",
            user=user,
            payment_type="one_time",
        )

        payload = {
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {"id": "PAYPAL777", "amount": {"value": "12.00", "currency_code": "USD"}},
        }
        response = handle_paypal_webhook(payload, "")
        assert response.get("success") is True

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status in ["succeeded", "partial"]
        assert "receipt_url" in payment.metadata

    def test_mobile_money_webhook_sets_receipt(self, db, user):
        service = PaymentService()
        service.providers["mobile_money"] = self._stub_provider("MMREC")
        result = service.create_payment(
            provider="mobile_money",
            amount=Decimal("6.00"),
            currency="USD",
            description="MM receipt",
            user=user,
            payment_type="one_time",
        )
        from apps.payments.providers import handle_mobile_money_webhook

        payload = {"ResultCode": 0, "MpesaReceiptNumber": "MMREC", "Amount": 6}
        handle_mobile_money_webhook(payload, "sig")

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.metadata.get("receipt_url")
