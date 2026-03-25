import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.payments.models import Payment, Plan, Subscription
from apps.referrals.models import Referral, ReferralCode


@pytest.mark.django_db
def test_admin_feature_access_includes_referrals_and_payments(admin_client):
    response = admin_client.get(reverse("admin_management:feature-access"))

    assert response.status_code == status.HTTP_200_OK
    permissions = response.data["permissions"]
    assert permissions["manage_referrals"] is True
    assert permissions["manage_payments"] is True


@pytest.mark.django_db
def test_admin_can_list_and_retrieve_referrals(admin_client):
    referrer = User.objects.create_user(
        email="referrer@example.com",
        password="testpass123",
        full_name="Referrer User",
        role="STUDENT",
    )
    referee = User.objects.create_user(
        email="referee@example.com",
        password="testpass123",
        full_name="Referee User",
        role="STUDENT",
    )
    code = ReferralCode.objects.create(user=referrer, code="ABCD1234")
    referral = Referral.objects.create(
        referrer=referrer,
        referee=referee,
        referral_code=code,
        email=referee.email,
        status="registered",
    )

    list_response = admin_client.get(reverse("admin_management:referral-list"))
    assert list_response.status_code == status.HTTP_200_OK
    assert any(
        item["id"] == str(referral.id) for item in list_response.data["results"]
    )

    detail_response = admin_client.get(
        reverse("admin_management:referral-detail", args=[referral.id])
    )
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["id"] == str(referral.id)
    assert detail_response.data["referral_code_value"] == code.code


@pytest.mark.django_db
def test_admin_can_list_and_retrieve_payments_and_subscriptions(admin_client):
    user = User.objects.create_user(
        email="billing-user@example.com",
        password="testpass123",
        full_name="Billing User",
        role="STUDENT",
    )
    plan = Plan.objects.create(
        name="Premium",
        tier="premium",
        price_monthly="10.00",
        price_yearly="100.00",
        billing_period="monthly",
    )
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        billing_period="monthly",
    )
    payment = Payment.objects.create(
        user=user,
        subscription=subscription,
        payment_type="subscription",
        amount="10.00",
        currency="USD",
        status="succeeded",
        description="Monthly subscription payment",
    )

    payment_list = admin_client.get(reverse("admin_management:admin-payment-list"))
    assert payment_list.status_code == status.HTTP_200_OK
    assert any(item["id"] == str(payment.id) for item in payment_list.data["results"])

    payment_detail = admin_client.get(
        reverse("admin_management:admin-payment-detail", args=[payment.id])
    )
    assert payment_detail.status_code == status.HTTP_200_OK
    assert payment_detail.data["id"] == str(payment.id)
    assert payment_detail.data["plan_name"] == plan.name

    subscription_list = admin_client.get(
        reverse("admin_management:admin-subscription-list")
    )
    assert subscription_list.status_code == status.HTTP_200_OK
    assert any(
        item["id"] == str(subscription.id)
        for item in subscription_list.data["results"]
    )

    subscription_detail = admin_client.get(
        reverse("admin_management:admin-subscription-detail", args=[subscription.id])
    )
    assert subscription_detail.status_code == status.HTTP_200_OK
    assert subscription_detail.data["id"] == str(subscription.id)
    assert subscription_detail.data["plan_name"] == plan.name
