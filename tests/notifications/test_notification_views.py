from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.notifications.models import Notification, NotificationType
from apps.notifications.views import NotificationViewSet

User = get_user_model()


def _create_notification(recipient, **overrides):
    data = {
        "recipient": recipient,
        "title": "System Notice",
        "message": "Test notification",
        "notification_type": NotificationType.SYSTEM,
        "is_read": False,
    }
    data.update(overrides)
    return Notification.objects.create(**data)


def test_notification_list_requires_authentication(api_client):
    url = reverse("notifications:notification-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_notification_list_is_user_scoped(authenticated_client, user):
    other_user = User.objects.create_user(
        email="other-notification-user@test.com",
        password="testpass123",
        full_name="Other User",
        registration_number="STU999",
        role="student",
    )
    baseline_count = Notification.objects.filter(recipient=user).count()

    mine_one = _create_notification(user, title="Mine One")
    mine_two = _create_notification(user, title="Mine Two")
    _create_notification(other_user, title="Other User Notification")

    url = reverse("notifications:notification-list")
    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == baseline_count + 2
    returned_ids = {item["id"] for item in response.data["results"]}
    assert {str(mine_one.id), str(mine_two.id)}.issubset(returned_ids)


def test_notification_list_filters_by_read_and_type(authenticated_client, user):
    baseline_matching_ids = set(
        Notification.objects.filter(
            recipient=user,
            is_read=False,
            notification_type=NotificationType.SYSTEM,
        ).values_list("id", flat=True)
    )

    unread_system = _create_notification(
        user,
        notification_type=NotificationType.SYSTEM,
    )
    _create_notification(
        user,
        notification_type=NotificationType.ANNOUNCEMENT,
        is_read=False,
    )
    _create_notification(
        user,
        notification_type=NotificationType.SYSTEM,
        is_read=True,
    )

    url = reverse("notifications:notification-list")
    response = authenticated_client.get(
        url,
        {"is_read": "false", "type": NotificationType.SYSTEM},
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {item["id"] for item in response.data["results"]}
    assert str(unread_system.id) in returned_ids
    assert returned_ids.issuperset({str(value) for value in baseline_matching_ids})
    assert all(item["is_read"] is False for item in response.data["results"])
    assert all(
        item["notification_type"] == NotificationType.SYSTEM
        for item in response.data["results"]
    )


def test_unread_count_endpoint_returns_expected_value(authenticated_client, user):
    baseline_unread = Notification.objects.filter(recipient=user, is_read=False).count()

    _create_notification(user, is_read=False)
    _create_notification(user, is_read=False)
    _create_notification(user, is_read=True)

    url = reverse("notifications:notification-unread-count")
    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["unread_count"] == baseline_unread + 2


def test_unread_endpoint_returns_only_unread(authenticated_client, user):
    baseline_unread_ids = set(
        Notification.objects.filter(recipient=user, is_read=False).values_list(
            "id",
            flat=True,
        )
    )

    unread_one = _create_notification(user, title="Unread One", is_read=False)
    unread_two = _create_notification(user, title="Unread Two", is_read=False)
    _create_notification(user, title="Read One", is_read=True)

    url = reverse("notifications:notification-unread")
    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {item["id"] for item in response.data}
    assert all(item["is_read"] is False for item in response.data)
    assert {str(unread_one.id), str(unread_two.id)}.issubset(returned_ids)
    assert returned_ids.issuperset({str(value) for value in baseline_unread_ids})


def test_mark_all_read_marks_all_unread(authenticated_client, user):
    unread_one = _create_notification(user, is_read=False)
    unread_two = _create_notification(user, is_read=False)

    url = reverse("notifications:notification-mark-all-read")
    response = authenticated_client.post(url, {})

    unread_one.refresh_from_db()
    unread_two.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert unread_one.is_read is True
    assert unread_two.is_read is True
    assert response.data["message"] == "All notifications marked as read."


def test_mark_multiple_read_marks_selected_only(authenticated_client, user):
    target_one = _create_notification(user, is_read=False)
    target_two = _create_notification(user, is_read=False)
    untouched = _create_notification(user, is_read=False)

    url = reverse("notifications:notification-mark-multiple-read")
    response = authenticated_client.post(
        url,
        {"notification_ids": [str(target_one.id), str(target_two.id)]},
        format="json",
    )

    target_one.refresh_from_db()
    target_two.refresh_from_db()
    untouched.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert target_one.is_read is True
    assert target_two.is_read is True
    assert untouched.is_read is False


def test_mark_multiple_read_without_ids_marks_all(authenticated_client, user):
    target_one = _create_notification(user, is_read=False)
    target_two = _create_notification(user, is_read=False)

    url = reverse("notifications:notification-mark-multiple-read")
    response = authenticated_client.post(url, {}, format="json")

    target_one.refresh_from_db()
    target_two.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert target_one.is_read is True
    assert target_two.is_read is True


def test_mark_read_marks_single_notification(authenticated_client, user):
    target = _create_notification(user, is_read=False)
    url = reverse("notifications:notification-mark-read", kwargs={"pk": target.id})
    response = authenticated_client.post(url, {})

    target.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert target.is_read is True
    assert response.data["id"] == str(target.id)
    assert response.data["is_read"] is True


def test_mark_read_returns_403_when_notification_not_owned(user):
    other_user = User.objects.create_user(
        email="other-owner@test.com",
        password="testpass123",
        full_name="Notification Owner",
        registration_number="STU998",
        role="student",
    )
    foreign_notification = _create_notification(other_user)

    factory = APIRequestFactory()
    request = factory.post("/api/notifications/any/mark_read/")
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"post": "mark_read"})

    with patch(
        "apps.notifications.views.NotificationViewSet.get_object",
        return_value=foreign_notification,
    ):
        response = view(request, pk=foreign_notification.id)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Not authorized."
