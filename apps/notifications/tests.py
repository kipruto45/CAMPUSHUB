"""
Tests for notifications app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification, DeviceToken, NotificationType, NotificationPriority

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestNotificationModel:
    """Tests for Notification model."""

    def test_notification_creation(self, user):
        """Test notification creation."""
        notification = Notification.objects.create(
            recipient=user,
            title="Test Notification",
            message="This is a test notification",
            notification_type=NotificationType.SYSTEM,
        )
        assert notification.id is not None
        assert notification.title == "Test Notification"
        assert notification.is_read is False

    def test_notification_str(self, user):
        """Test notification string representation."""
        notification = Notification.objects.create(
            recipient=user,
            title="Test Notification",
            message="Test",
        )
        assert user.email in str(notification)

    def test_notification_type_display(self, user):
        """Test notification_type_display property."""
        notification = Notification.objects.create(
            recipient=user,
            title="Test Notification",
            message="Test",
            notification_type=NotificationType.NEW_RESOURCE,
        )
        assert "New Resource" in notification.notification_type_display


@pytest.mark.django_db
class TestDeviceTokenModel:
    """Tests for DeviceToken model."""

    def test_device_token_creation(self, user):
        """Test device token creation."""
        token = DeviceToken.objects.create(
            user=user,
            device_token="test_device_token_123",
            device_type="android",
        )
        assert token.id is not None
        assert token.device_token == "test_device_token_123"
        assert token.is_active is True

    def test_device_token_str(self, user):
        """Test device token string representation."""
        token = DeviceToken.objects.create(
            user=user,
            device_token="test_device_token_123",
            device_type="android",
        )
        assert "android" in str(token)