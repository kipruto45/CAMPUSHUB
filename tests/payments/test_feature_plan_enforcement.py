import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payments.models import Plan, Subscription


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="feature-access@example.com",
        password="testpass123",
        is_verified=True,
    )


def _create_plan(*, tier: str, name: str) -> Plan:
    price_monthly = {
        "basic": 5.99,
        "premium": 12.00,
    }[tier]
    price_yearly = {
        "basic": 59.99,
        "premium": 120.00,
    }[tier]
    storage_limit_gb = {
        "basic": 10,
        "premium": 100,
    }[tier]
    max_upload_size_mb = {
        "basic": 50,
        "premium": 250,
    }[tier]
    return Plan.objects.create(
        name=name,
        tier=tier,
        price_monthly=price_monthly,
        price_yearly=price_yearly,
        storage_limit_gb=storage_limit_gb,
        max_upload_size_mb=max_upload_size_mb,
        is_active=True,
    )


@pytest.mark.django_db
def test_versioned_cloud_storage_blocks_free_plan(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/v1/cloud-storage/google/status/")

    assert response.status_code == 403
    assert response.data["feature"] == "all_integrations"


@pytest.mark.django_db
def test_versioned_cloud_storage_allows_premium_plan(api_client, user):
    premium_plan = _create_plan(tier="premium", name="Premium")
    Subscription.objects.create(
        user=user,
        plan=premium_plan,
        status="active",
    )
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/v1/cloud-storage/google/status/")

    assert response.status_code == 200
    assert response.data["connected"] is False


@pytest.mark.django_db
def test_course_progress_blocks_free_plan(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("courses:course-progress-list"))

    assert response.status_code == 403
    assert response.data["feature"] == "advanced_analytics"


@pytest.mark.django_db
def test_course_progress_allows_basic_plan(api_client, user):
    basic_plan = _create_plan(tier="basic", name="Basic")
    Subscription.objects.create(
        user=user,
        plan=basic_plan,
        status="active",
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("courses:course-progress-list"))

    assert response.status_code == 200
    assert response.data == []
