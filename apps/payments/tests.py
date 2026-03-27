"""
Tests for payment WebSocket and webhook functionality.
"""

import base64
import json
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from decimal import Decimal

from apps.payments.models import Plan, Subscription, Payment
from apps.payments.notifications import PaymentNotificationService
from apps.payments.services import StripeService, InAppPurchaseService
from apps.payments.providers import PayPalPaymentProvider, PaymentService
from apps.payments.providers import handle_paypal_webhook, handle_mobile_money_webhook
from apps.payments.views import payment_service


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
        assert "providers" in response.data
        assert len(response.data["plans"]) >= 1

    def test_get_plans_includes_plan_types_and_extended_limits(self, api_client, user, plan):
        api_client.force_authenticate(user=user)

        plan.upload_limit_monthly = 180
        plan.message_limit_daily = 500
        plan.group_limit = 30
        plan.bookmark_limit = 500
        plan.search_results_limit = 100
        plan.support_response_hours = 8
        plan.metadata = {
            "plan_type": "Power",
            "ideal_for": "Heavy contributors and study leaders.",
            "highlights": ["Large upload cap", "Certificates", "Priority perks"],
        }
        plan.save(
            update_fields=[
                "upload_limit_monthly",
                "message_limit_daily",
                "group_limit",
                "bookmark_limit",
                "search_results_limit",
                "support_response_hours",
                "metadata",
                "updated_at",
            ]
        )

        response = api_client.get("/api/payments/plans/")

        assert response.status_code == 200
        payload = next(item for item in response.data["plans"] if item["id"] == str(plan.id))
        assert payload["plan_type"] == "Power"
        assert payload["ideal_for"] == "Heavy contributors and study leaders."
        assert payload["highlights"] == ["Large upload cap", "Certificates", "Priority perks"]
        assert payload["upload_limit_monthly"] == 180
        assert payload["message_limit_daily"] == 500
        assert payload["group_limit"] == 30
        assert payload["bookmark_limit"] == 500
        assert payload["search_results_limit"] == 100
        assert payload["support_response_hours"] == 8
        assert payload["trial_preview"]["available"] is True
        assert "limits" in payload

    def test_get_payment_provider_statuses(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/payments/providers/")

        assert response.status_code == 200
        assert "providers" in response.data
        assert "stripe" in response.data["providers"]
        assert "paypal" in response.data["providers"]
        assert "mobile_money" in response.data["providers"]

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

    def test_create_subscription_with_generic_provider_links_payment(self, api_client, user, plan):
        api_client.force_authenticate(user=user)

        class StubProvider:
            def create_payment(self, amount, currency, metadata):
                return {
                    "success": True,
                    "payment_id": "PAYPAL-SUB-001",
                    "checkout_url": "https://example.com/paypal/checkout",
                }

            def verify_payment(self, payment_id):
                return {"success": True, "status": "COMPLETED"}

            def process_webhook(self, payload, signature):
                return {"success": True, "event_type": "PAYMENT.CAPTURE.COMPLETED", "data": {}}

            def refund_payment(self, payment_id, amount=None):
                return {"success": True}

        with patch.dict(payment_service.providers, {"paypal": StubProvider()}, clear=False):
            response = api_client.post(
                "/api/payments/subscription/",
                {
                    "plan_id": str(plan.id),
                    "billing_period": "monthly",
                    "provider": "paypal",
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["provider"] == "paypal"
        assert response.data["checkout_url"] == "https://example.com/paypal/checkout"

        subscription = Subscription.objects.get(id=response.data["subscription_id"])
        payment = Payment.objects.get(id=response.data["payment_id"])

        assert payment.subscription_id == subscription.id
        assert payment.payment_type == "subscription"
        assert payment.metadata.get("provider") == "paypal"
        assert subscription.status == "unpaid"

    def test_get_subscription_syncs_pending_paypal_payment(self, api_client, user, plan):
        api_client.force_authenticate(user=user)

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            billing_period="monthly",
            status="unpaid",
        )
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            amount=plan.price_monthly,
            currency="USD",
            payment_type="subscription",
            status="pending",
            stripe_payment_intent_id="PAYPAL-SUB-VERIFY",
            metadata={
                "provider": "paypal",
                "provider_payment_id": "PAYPAL-SUB-VERIFY",
            },
        )

        def fake_verify(provider, payment_id):
            assert provider == "paypal"
            assert payment_id == "PAYPAL-SUB-VERIFY"
            payment_service.process_successful_payment(
                "paypal",
                "PAYPAL-SUB-VERIFY",
                Decimal("9.99"),
                "USD",
            )
            return {
                "success": True,
                "status": "COMPLETED",
                "amount": Decimal("9.99"),
                "currency": "USD",
                "order_id": "PAYPAL-SUB-VERIFY",
                "capture_id": "CAPTURE-SUB-1",
            }

        with patch.object(payment_service, "verify_payment", side_effect=fake_verify) as mock_verify:
            response = api_client.get("/api/payments/subscription/")

        assert response.status_code == 200
        assert response.data["subscription"]["status"] == "active"
        mock_verify.assert_called_once_with("paypal", "PAYPAL-SUB-VERIFY")

        payment.refresh_from_db()
        subscription.refresh_from_db()
        assert payment.status == "succeeded"
        assert subscription.status == "active"

    def test_start_trial_sets_trial_start_and_blocks_reuse(self, api_client, user, plan):
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/payments/trial/", {}, format="json")

        assert response.status_code == 200
        assert response.data["tier"] == "basic"
        assert response.data["duration_days"] == 7
        subscription = Subscription.objects.get(id=response.data["subscription_id"])
        assert subscription.status == "trialing"
        assert subscription.plan.tier == "basic"
        assert subscription.trial_start is not None
        assert subscription.trial_end is not None
        assert subscription.metadata.get("trial") is True
        assert subscription.metadata.get("trial_duration_days") == 7

        second_response = api_client.post("/api/payments/trial/", {}, format="json")
        assert second_response.status_code == 400
        assert "already used your trial" in second_response.data["error"].lower()

    def test_trial_feature_access_uses_reduced_limits_and_locked_features(self, api_client, user):
        api_client.force_authenticate(user=user)

        start_response = api_client.post("/api/payments/trial/", {}, format="json")
        assert start_response.status_code == 200

        response = api_client.get("/api/payments/feature-access/")

        assert response.status_code == 200
        assert response.data["is_trial"] is True
        assert response.data["is_trial_limited"] is True
        assert response.data["upload_limit_monthly"] == 12
        assert response.data["download_limit_monthly"] == 80
        assert response.data["message_limit_daily"] == 40
        assert response.data["group_limit"] == 3
        assert response.data["support_response_hours"] == 48
        assert "export_reports" in response.data["trial_locked_features"]
        assert "phone_support" in response.data["trial_locked_features"]

    def test_admin_trial_uses_premium_for_seven_days(self, api_client):
        admin_user = get_user_model().objects.create_user(
            email="billing-admin@example.com",
            password="testpass123",
            role="ADMIN",
        )
        api_client.force_authenticate(user=admin_user)

        response = api_client.post("/api/payments/trial/", {}, format="json")

        assert response.status_code == 200
        assert response.data["tier"] == "premium"
        assert response.data["duration_days"] == 7
        subscription = Subscription.objects.get(id=response.data["subscription_id"])
        assert subscription.plan.tier == "premium"

    def test_expired_trial_downgrades_user_and_sends_upgrade_notifications(
        self,
        api_client,
        user,
        mailoutbox,
    ):
        api_client.force_authenticate(user=user)
        user.phone_number = "+254700000001"
        user.save(update_fields=["phone_number", "updated_at"])

        trial_response = api_client.post("/api/payments/trial/", {}, format="json")
        subscription = Subscription.objects.get(id=trial_response.data["subscription_id"])
        expired_at = timezone.now() - timezone.timedelta(minutes=5)
        started_at = expired_at - timezone.timedelta(days=7)
        subscription.status = "trialing"
        subscription.trial_start = started_at
        subscription.trial_end = expired_at
        subscription.current_period_start = started_at
        subscription.current_period_end = expired_at
        subscription.metadata = {
            "trial": True,
            "trial_duration_days": 7,
        }
        subscription.save(
            update_fields=[
                "status",
                "trial_start",
                "trial_end",
                "current_period_start",
                "current_period_end",
                "metadata",
                "updated_at",
            ]
        )

        with patch(
            "apps.core.sms.sms_service.send_trial_expired_notice",
            return_value={"success": True},
        ) as mock_sms:
            response = api_client.get("/api/payments/feature-access/")
            second_response = api_client.get("/api/payments/feature-access/")

        subscription.refresh_from_db()

        assert response.status_code == 200
        assert second_response.status_code == 200
        assert response.data["tier"] == "free"
        assert response.data["trial_expired"] is True
        assert response.data["show_upgrade_prompt"] is True
        assert subscription.status == "canceled"
        assert len(mailoutbox) == 1
        assert "free trial has ended" in mailoutbox[0].subject.lower()
        assert mock_sms.call_count == 1


@pytest.mark.django_db
class TestPaymentNotificationLinks:
    def test_trial_expired_email_uses_current_plans_link(self, settings, user, mailoutbox):
        settings.FRONTEND_BASE_URL = "https://campushub.example"
        settings.FRONTEND_URL = ""

        sent = PaymentNotificationService.send_trial_expired_email(user, "Basic")

        assert sent is True
        assert len(mailoutbox) == 1
        html = mailoutbox[0].alternatives[0][0]
        assert "https://campushub.example/billing/plans" in html
        assert "/settings/billing/" not in html

    def test_payment_due_reminder_email_uses_current_pay_link(self, settings, user, mailoutbox):
        settings.FRONTEND_BASE_URL = "https://campushub.example"
        settings.FRONTEND_URL = ""

        sent = PaymentNotificationService.send_payment_due_reminder_email(
            user=user,
            amount=Decimal("12.00"),
            currency="USD",
            due_date="2026-03-31",
            description="Storage renewal",
        )

        assert sent is True
        assert len(mailoutbox) == 1
        html = mailoutbox[0].alternatives[0][0]
        assert "https://campushub.example/billing/pay" in html

    def test_storage_upgrade_confirmation_email_uses_storage_link(self, settings, user, mailoutbox):
        settings.FRONTEND_BASE_URL = "https://campushub.example"
        settings.FRONTEND_URL = ""

        sent = PaymentNotificationService.send_storage_upgrade_confirmation_email(
            user=user,
            storage_gb=25,
            duration_days=30,
            amount=Decimal("4.99"),
            currency="USD",
        )

        assert sent is True
        assert len(mailoutbox) == 1
        html = mailoutbox[0].alternatives[0][0]
        assert "https://campushub.example/storage" in html

    def test_payment_buttons_use_real_backend_fallback_urls_without_frontend(
        self,
        settings,
        user,
        mailoutbox,
    ):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""
        settings.BASE_URL = "https://api.campushub.example"

        assert PaymentNotificationService.send_trial_expired_email(user, "Basic") is True
        assert PaymentNotificationService.send_payment_due_reminder_email(
            user=user,
            amount=Decimal("12.00"),
            currency="USD",
            due_date="2026-03-31",
            description="Storage renewal",
        ) is True
        assert PaymentNotificationService.send_subscription_activated_email(
            user=user,
            plan_name="Premium",
            billing_period="monthly",
            amount=Decimal("9.99"),
            currency="USD",
        ) is True
        assert PaymentNotificationService.send_refund_notification_email(
            user=user,
            amount=Decimal("3.50"),
            currency="USD",
            payment_id="pay_123",
            reason="Duplicate payment",
        ) is True
        assert PaymentNotificationService.send_storage_upgrade_confirmation_email(
            user=user,
            storage_gb=25,
            duration_days=30,
            amount=Decimal("4.99"),
            currency="USD",
        ) is True

        html_messages = [message.alternatives[0][0] for message in mailoutbox]
        combined_html = "\n".join(html_messages)

        assert 'href="#"' not in combined_html
        assert "https://api.campushub.example/api/payments/plans/" in combined_html
        assert "https://api.campushub.example/api/payments/payments/" in combined_html
        assert "https://api.campushub.example/api/payments/subscription/" in combined_html
        assert "https://api.campushub.example/api/payments/storage/" in combined_html


@pytest.mark.django_db
def test_seed_default_plans_uses_env_backed_stripe_ids(monkeypatch):
    monkeypatch.setenv("STRIPE_BASIC_MONTHLY_PRICE_ID", "price_basic_monthly_live")
    monkeypatch.setenv("STRIPE_BASIC_YEARLY_PRICE_ID", "price_basic_yearly_live")
    monkeypatch.setenv("STRIPE_BASIC_PRODUCT_ID", "prod_basic_live")

    call_command("seed_default_plans")

    plan = Plan.objects.get(tier="basic", is_active=True)
    assert plan.stripe_monthly_price_id == "price_basic_monthly_live"
    assert plan.stripe_yearly_price_id == "price_basic_yearly_live"
    assert plan.stripe_product_id == "prod_basic_live"


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

    def test_verify_payment_reconciles_completed_paypal_order(self, db, user):
        class PayPalStub:
            def create_payment(self, amount, currency, metadata):
                return {
                    "success": True,
                    "payment_id": "PAYPALORDER123",
                    "checkout_url": "http://example.com/paypal",
                }

            def verify_payment(self, payment_id):
                return {
                    "success": True,
                    "status": "COMPLETED",
                    "amount": Decimal("10.00"),
                    "currency": "USD",
                    "order_id": "PAYPALORDER123",
                    "capture_id": "CAPTURE123",
                }

            def process_webhook(self, payload, signature):
                return {"success": True, "event_type": "PAYMENT.CAPTURE.COMPLETED", "data": {}}

            def refund_payment(self, payment_id, amount=None):
                return {"success": True}

        service = PaymentService()
        service.providers["paypal"] = PayPalStub()

        result = service.create_payment(
            provider="paypal",
            amount=Decimal("10.00"),
            currency="USD",
            description="Test PayPal verify",
            user=user,
            payment_type="one_time",
        )

        verify_result = service.verify_payment("paypal", "PAYPALORDER123")

        assert verify_result["success"] is True
        assert verify_result["status"] == "COMPLETED"

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status == "succeeded"
        assert payment.metadata.get("paypal_order_id") == "PAYPALORDER123"
        assert payment.metadata.get("paypal_capture_id") == "CAPTURE123"
        assert payment.stripe_charge_id == "CAPTURE123"

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

    def test_create_payment_accepts_mpesa_alias(self, db, user):
        service = PaymentService()
        service.providers["mobile_money"] = self._stub_provider("MPESA_ALIAS_001")

        result = service.create_payment(
            provider="mpesa",
            amount=Decimal("7.00"),
            currency="KES",
            description="M-Pesa alias",
            user=user,
            payment_type="one_time",
            phone_number="0712345678",
        )

        assert result["success"] is True
        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.metadata.get("provider") == "mobile_money"
        assert payment.metadata.get("provider_payment_id") == "MPESA_ALIAS_001"

    def test_create_payment_for_mobile_money_forces_kes_currency(self, db, user):
        captured = {}

        class Stub:
            def create_payment(self, amount, currency, metadata):
                captured["currency"] = currency
                return {
                    "success": True,
                    "payment_id": "MMKES001",
                    "checkout_url": None,
                    "instructions": {"message": "stub"},
                }

            def verify_payment(self, payment_id):
                return {"success": True, "status": "COMPLETED"}

            def process_webhook(self, payload, signature):
                return {"success": True, "event_type": "COMPLETED", "data": {}}

            def refund_payment(self, payment_id, amount=None):
                return {"success": True}

        service = PaymentService()
        service.providers["mobile_money"] = Stub()

        result = service.create_payment(
            provider="mobile_money",
            amount=Decimal("15.00"),
            currency="USD",
            description="Force KES",
            user=user,
            payment_type="one_time",
            phone_number="0712345678",
        )

        assert result["success"] is True
        assert captured["currency"] == "KES"

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.currency == "KES"

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
            "resource": {
                "id": "CAPTURE777",
                "amount": {"value": "12.00", "currency_code": "USD"},
                "supplementary_data": {
                    "related_ids": {
                        "order_id": "PAYPAL777",
                    }
                },
            },
        }
        response = handle_paypal_webhook(payload, "")
        assert response.get("success") is True

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status in ["succeeded", "partial"]
        assert "receipt_url" in payment.metadata
        assert payment.metadata.get("paypal_order_id") == "PAYPAL777"
        assert payment.metadata.get("paypal_capture_id") == "CAPTURE777"

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

    def test_mobile_money_webhook_nested_stk_callback(self, db, user):
        service = PaymentService()
        service.providers["mobile_money"] = self._stub_provider("ws_CO_ABC123")
        result = service.create_payment(
            provider="mobile_money",
            amount=Decimal("8.00"),
            currency="KES",
            description="MM nested callback",
            user=user,
            payment_type="one_time",
            phone_number="0712345678",
        )

        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_ABC123",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 8},
                            {"Name": "MpesaReceiptNumber", "Value": "TQ8123XYZ"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        response = handle_mobile_money_webhook(payload, "")
        assert response.get("success") is True

        payment = Payment.objects.get(id=result["local_payment_id"])
        assert payment.status in ["succeeded", "partial"]
        assert payment.metadata.get("mpesa_receipt_number") == "TQ8123XYZ"


@pytest.mark.django_db
def test_mpesa_stk_push_create_payment_success(settings, user):
    settings.MOBILE_MONEY_PROVIDER = "mpesa"
    settings.MOBILE_MONEY_SHORT_CODE = "174379"
    settings.MOBILE_MONEY_CONSUMER_KEY = "consumer-key"
    settings.MOBILE_MONEY_CONSUMER_SECRET = "consumer-secret"
    settings.MOBILE_MONEY_PASSKEY = "passkey"
    settings.MOBILE_MONEY_ENV = "sandbox"
    settings.MOBILE_MONEY_CALLBACK_URL = "https://api.example.com/api/payments/webhook/mobile-money/"
    settings.MOBILE_MONEY_TIMEOUT_SECONDS = 10
    settings.BASE_URL = "https://api.example.com"

    class MockResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        @property
        def ok(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    with patch(
        "requests.get",
        return_value=MockResponse(200, {"access_token": "test-token"}),
    ) as token_request, patch(
        "requests.post",
        return_value=MockResponse(
            200,
            {
                "ResponseCode": "0",
                "ResponseDescription": "Success. Request accepted for processing",
                "MerchantRequestID": "29115-34620561-1",
                "CheckoutRequestID": "ws_CO_999999",
                "CustomerMessage": "Success. Request accepted for processing",
            },
        ),
    ) as stk_request:
        service = PaymentService()
        result = service.create_payment(
            provider="mpesa",
            amount=Decimal("100.00"),
            currency="KES",
            description="Subscription payment",
            user=user,
            payment_type="one_time",
            phone_number="0712345678",
        )

    assert token_request.called
    assert stk_request.called
    assert result["success"] is True
    assert result["payment_id"] == "ws_CO_999999"

    payment = Payment.objects.get(id=result["local_payment_id"])
    assert payment.metadata.get("provider") == "mobile_money"
    assert payment.metadata.get("provider_payment_id") == "ws_CO_999999"


def test_paypal_provider_verify_payment_captures_approved_order(settings):
    settings.PAYPAL_CLIENT_ID = "paypal-client-id"
    settings.PAYPAL_CLIENT_SECRET = "paypal-client-secret"
    provider = PayPalPaymentProvider()

    class MockResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        @property
        def ok(self):
            return 200 <= self.status_code < 300

        def json(self):
            return self._payload

    approved_order = {
        "id": "ORDER123",
        "status": "APPROVED",
        "purchase_units": [
            {
                "reference_id": "local-payment-id",
                "custom_id": "local-payment-id",
                "amount": {"value": "19.99", "currency_code": "USD"},
            }
        ],
    }
    completed_order = {
        "id": "ORDER123",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": "local-payment-id",
                "custom_id": "local-payment-id",
                "amount": {"value": "19.99", "currency_code": "USD"},
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE123",
                            "amount": {"value": "19.99", "currency_code": "USD"},
                        }
                    ]
                },
            }
        ],
    }

    with patch.object(provider, "_get_access_token", return_value="test-token"), patch(
        "requests.get",
        return_value=MockResponse(200, approved_order),
    ) as order_request, patch(
        "requests.post",
        return_value=MockResponse(201, completed_order),
    ) as capture_request:
        result = provider.verify_payment("ORDER123")

    assert order_request.called
    assert capture_request.called
    assert result["success"] is True
    assert result["status"] == "COMPLETED"
    assert result["order_id"] == "ORDER123"
    assert result["capture_id"] == "CAPTURE123"


def test_validate_apple_receipt_uses_verify_receipt(settings):
    settings.APPLE_IAP_SHARED_SECRET = "apple-secret"
    settings.APPLE_IAP_USE_SANDBOX = True

    class MockResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = json.dumps(payload)
            self.content = self.text.encode()

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    payload = {
        "status": 0,
        "latest_receipt_info": [
            {
                "product_id": "apple.monthly",
                "transaction_id": "tx_123",
                "original_transaction_id": "otx_123",
                "expires_date_ms": "1730000000000",
            }
        ],
    }

    with patch("apps.payments.services.requests.post", return_value=MockResponse(payload)) as req:
        service = InAppPurchaseService()
        result = service.validate_apple_receipt(base64.b64encode(b"{}").decode("utf-8"))

    assert req.called
    assert result["success"] is True
    assert result["validation_source"] == "apple_verify_receipt"
    assert result["product_id"] == "apple.monthly"
    assert result["transaction_id"] == "tx_123"


def test_validate_apple_receipt_falls_back_without_secret(settings):
    settings.APPLE_IAP_SHARED_SECRET = ""
    receipt_payload = {
        "productId": "apple.yearly",
        "transactionId": "tx_abc",
        "originalTransactionId": "otx_abc",
        "expires_date_ms": "1730000000000",
    }
    receipt_data = base64.b64encode(json.dumps(receipt_payload).encode("utf-8")).decode("utf-8")

    service = InAppPurchaseService()
    result = service.validate_apple_receipt(receipt_data)

    assert result["success"] is True
    assert result["validation_source"] == "fallback"
    assert result["product_id"] == "apple.yearly"
    assert result["transaction_id"] == "tx_abc"


@pytest.mark.django_db
def test_validate_google_purchase_fallback_without_service_account(settings):
    settings.GOOGLE_PLAY_PACKAGE_NAME = ""
    settings.GOOGLE_PLAY_STRICT_VALIDATION = False

    service = InAppPurchaseService()
    result = service.validate_google_purchase("google.monthly", "token-123")

    assert result["success"] is True
    assert result["validation_source"] == "fallback"


@pytest.mark.django_db
def test_validate_google_purchase_strict_requires_service_account(settings):
    settings.GOOGLE_PLAY_PACKAGE_NAME = "com.example.app"
    settings.GOOGLE_PLAY_STRICT_VALIDATION = True

    service = InAppPurchaseService()
    with patch.object(service, "_get_google_access_token", return_value=""):
        result = service.validate_google_purchase("google.monthly", "token-123")

    assert result["success"] is False
