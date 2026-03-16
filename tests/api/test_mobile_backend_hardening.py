"""Regression tests for mobile backend hardening guarantees."""

import pytest
from django.urls import reverse

from apps.notifications.models import DeviceToken, Notification, NotificationType
from apps.resources.models import Resource


@pytest.mark.django_db
def test_mobile_response_headers_include_request_id_and_api_version(api_client):
    response = api_client.get("/api/mobile/info/")

    assert response.status_code == 200
    assert response["X-Request-ID"]
    assert response["X-API-Version"] == "1.0"


@pytest.mark.django_db
def test_mobile_resources_sorting_and_limit_clamp(authenticated_client, course, user):
    high = Resource.objects.create(
        title="High Downloads",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        download_count=99,
    )
    Resource.objects.create(
        title="Low Downloads",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        download_count=2,
    )

    response = authenticated_client.get(
        "/api/mobile/resources/",
        {"sort": "downloads", "limit": 200},
    )
    assert response.status_code == 200

    payload = response.data["data"]
    assert payload["pagination"]["limit"] == 50
    assert payload["resources"][0]["id"] == high.id


@pytest.mark.django_db
def test_mobile_device_register_is_idempotent(authenticated_client):
    url = reverse("api:mobile_register_device")
    data = {
        "device_token": "idempotent_token_123",
        "device_type": "android",
        "device_name": "Pixel",
        "device_model": "7 Pro",
    }
    headers = {"HTTP_X_IDEMPOTENCY_KEY": "device-register-1"}

    first = authenticated_client.post(url, data, format="json", **headers)
    second = authenticated_client.post(url, data, format="json", **headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first["X-Idempotent-Replay"] == "false"
    assert second["X-Idempotent-Replay"] == "true"
    assert DeviceToken.objects.filter(device_token="idempotent_token_123").count() == 1


@pytest.mark.django_db
def test_mobile_mark_notification_read_is_idempotent(authenticated_client, user):
    notification = Notification.objects.create(
        recipient=user,
        title="Test Notification",
        message="Please read me",
        notification_type=NotificationType.SYSTEM,
    )
    url = reverse(
        "api:mobile_mark_notification_read",
        kwargs={"notification_id": notification.id},
    )
    headers = {"HTTP_X_IDEMPOTENCY_KEY": "mark-read-1"}

    first = authenticated_client.post(url, {}, format="json", **headers)
    second = authenticated_client.post(url, {}, format="json", **headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first["X-Idempotent-Replay"] == "false"
    assert second["X-Idempotent-Replay"] == "true"

    notification.refresh_from_db()
    assert notification.is_read is True
