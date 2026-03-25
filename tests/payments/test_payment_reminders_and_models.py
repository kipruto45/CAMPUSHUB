from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.payments.models import (
    FeatureUnlock,
    InAppProduct,
    InAppPurchase,
    Invoice,
    Payment,
    Plan,
    PromoCode,
)
from apps.payments.notifications import send_payment_due_reminders


@pytest.mark.django_db
def test_send_payment_due_reminders_updates_payment_metadata(user):
    payment = Payment.objects.create(
        user=user,
        payment_type="one_time",
        amount=Decimal("25.00"),
        currency="USD",
        status="pending",
        metadata={"due_date": (timezone.now() + timedelta(days=1)).isoformat()},
    )

    with patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_email",
        return_value=True,
    ) as mock_email, patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_sms",
        return_value=True,
    ) as mock_sms:
        sent_count = send_payment_due_reminders()

    payment.refresh_from_db()
    assert sent_count == 1
    assert mock_email.call_count == 1
    assert mock_sms.call_count == 0
    assert payment.metadata["reminders"]["payment_due_last_sent_at"]


@pytest.mark.django_db
def test_send_payment_due_reminders_updates_invoice_metadata(user):
    invoice = Invoice.objects.create(
        user=user,
        invoice_number="INV-TEST-001",
        amount=Decimal("40.00"),
        currency="USD",
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        status="open",
        due_date=timezone.now() + timedelta(days=2),
        description="Monthly billing",
    )

    with patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_email",
        return_value=True,
    ) as mock_email, patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_sms",
        return_value=True,
    ) as mock_sms:
        sent_count = send_payment_due_reminders()

    invoice.refresh_from_db()
    assert sent_count == 1
    assert mock_email.call_count == 1
    assert mock_sms.call_count == 0
    assert invoice.metadata["reminders"]["invoice_due_last_sent_at"]


@pytest.mark.django_db
def test_send_payment_due_reminders_is_daily_idempotent(user):
    payment = Payment.objects.create(
        user=user,
        payment_type="one_time",
        amount=Decimal("15.00"),
        currency="USD",
        status="pending",
        metadata={"due_date": (timezone.now() + timedelta(days=1)).isoformat()},
    )

    with patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_email",
        return_value=True,
    ):
        first_run = send_payment_due_reminders()
    with patch(
        "apps.payments.notifications.PaymentNotificationService.send_payment_due_reminder_email",
        return_value=True,
    ):
        second_run = send_payment_due_reminders()

    payment.refresh_from_db()
    assert first_run == 1
    assert second_run == 0
    assert payment.metadata["reminders"]["payment_due_last_sent_at"]


@pytest.mark.django_db
def test_promo_code_is_valid_respects_window_and_usage():
    now = timezone.now()
    promo = PromoCode.objects.create(
        code="WELCOME20",
        description="Welcome discount",
        discount_type="percentage",
        discount_value=Decimal("20.00"),
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        max_uses=1,
        current_uses=0,
    )

    assert promo.is_valid is True
    promo.current_uses = 1
    promo.save(update_fields=["current_uses"])
    assert promo.is_valid is False


@pytest.mark.django_db
def test_in_app_purchase_is_active_depends_on_expiry(user):
    product = InAppProduct.objects.create(
        name="Premium Monthly",
        description="Premium monthly subscription",
        platform="google",
        product_type="subscription",
        subscription_type="monthly",
        price=Decimal("9.99"),
        currency="USD",
        google_product_id="premium.monthly",
        tier="premium",
    )

    active_purchase = InAppPurchase.objects.create(
        user=user,
        product=product,
        platform="google",
        google_purchase_token="token-active",
        status="active",
        is_subscription=True,
        subscription_type="monthly",
        period_start=timezone.now() - timedelta(days=1),
        period_end=timezone.now() + timedelta(days=29),
        expires_date=timezone.now() + timedelta(days=29),
        amount=Decimal("9.99"),
        currency="USD",
    )
    expired_purchase = InAppPurchase.objects.create(
        user=user,
        product=product,
        platform="google",
        google_purchase_token="token-expired",
        status="active",
        is_subscription=True,
        subscription_type="monthly",
        period_start=timezone.now() - timedelta(days=40),
        period_end=timezone.now() - timedelta(days=10),
        expires_date=timezone.now() - timedelta(days=10),
        amount=Decimal("9.99"),
        currency="USD",
    )

    assert active_purchase.is_active is True
    assert expired_purchase.is_active is False


@pytest.mark.django_db
def test_feature_unlock_is_currently_active(user):
    product = InAppProduct.objects.create(
        name="Dark Theme Unlock",
        description="Unlock dark theme",
        platform="apple",
        product_type="feature_unlock",
        price=Decimal("2.99"),
        currency="USD",
        apple_product_id="feature.darktheme",
        feature_key="dark_theme",
    )
    purchase = InAppPurchase.objects.create(
        user=user,
        product=product,
        platform="apple",
        apple_transaction_id="txn-feature-001",
        status="active",
        amount=Decimal("2.99"),
        currency="USD",
    )
    unlock = FeatureUnlock.objects.create(
        user=user,
        feature_key="dark_theme",
        feature_name="Dark Theme",
        purchase=purchase,
        is_active=True,
        expires_at=timezone.now() + timedelta(days=7),
    )

    assert unlock.is_currently_active is True
    unlock.expires_at = timezone.now() - timedelta(days=1)
    unlock.save(update_fields=["expires_at"])
    assert unlock.is_currently_active is False


@pytest.mark.django_db
def test_plan_and_promo_code_many_to_many_relation():
    now = timezone.now()
    plan = Plan.objects.create(
        name="Premium",
        tier="premium",
        price_monthly=Decimal("9.99"),
        price_yearly=Decimal("99.99"),
        billing_period="monthly",
    )
    promo = PromoCode.objects.create(
        code="PREMIUM5",
        description="Premium plan discount",
        discount_type="fixed",
        discount_value=Decimal("5.00"),
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    promo.applicable_plans.add(plan)

    assert promo.applicable_plans.filter(id=plan.id).exists()
