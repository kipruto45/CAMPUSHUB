import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.notifications.models import Notification, NotificationType
from apps.resources.models import Resource


@pytest.fixture
def notification_user(db):
    return User.objects.create_user(
        email="mobile-notification@example.com",
        password="testpass123",
        full_name="Mobile Notification User",
    )


@pytest.fixture
def notification_client(notification_user):
    client = APIClient()
    refresh = RefreshToken.for_user(notification_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
def test_mobile_notifications_include_resource_metadata(notification_client, notification_user):
    resource = Resource.objects.create(
        title="Distributed Systems Notes",
        uploaded_by=notification_user,
        status="approved",
        is_public=True,
    )
    notification = Notification.objects.create(
        recipient=notification_user,
        title="Resource approved",
        message="Your upload is now available to other students.",
        notification_type=NotificationType.RESOURCE_APPROVED,
        link=f"/(student)/resource/{resource.id}",
        target_resource=resource,
    )

    response = notification_client.get("/api/mobile/notifications/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    matching = next(
        item
        for item in response.data["data"]["notifications"]
        if item["id"] == str(notification.id)
    )
    assert matching == {
        "id": str(notification.id),
        "title": "Resource approved",
        "message": "Your upload is now available to other students.",
        "type": NotificationType.RESOURCE_APPROVED,
        "notification_type_display": "Resource Approved",
        "is_read": False,
        "link": f"/(student)/resource/{resource.id}",
        "resource_id": str(resource.id),
        "created_at": notification.created_at.isoformat(),
    }


@pytest.mark.django_db
def test_mobile_mark_all_notifications_read_marks_everything(notification_client, notification_user):
    Notification.objects.create(
        recipient=notification_user,
        title="First",
        message="Unread one",
        notification_type=NotificationType.SYSTEM,
        is_read=False,
    )
    Notification.objects.create(
        recipient=notification_user,
        title="Second",
        message="Unread two",
        notification_type=NotificationType.ANNOUNCEMENT,
        is_read=False,
    )
    unread_before = Notification.objects.filter(
        recipient=notification_user,
        is_read=False,
    ).count()

    response = notification_client.post("/api/mobile/notifications/read-all/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["data"] == {
        "deleted_count": unread_before,
        "unread_count": 0,
    }
    assert Notification.objects.filter(recipient=notification_user).count() == 0
