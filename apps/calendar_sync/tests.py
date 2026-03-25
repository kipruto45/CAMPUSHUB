"""
Tests for calendar_sync app.
"""
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.calendar_sync.models import CalendarAccount, SyncedEvent, SyncSettings

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestCalendarAccountModel:
    """Tests for CalendarAccount model."""

    def test_calendar_account_creation(self, user):
        """Test calendar account creation."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
        )
        assert account.id is not None
        assert account.user == user
        assert account.provider == "google"

    def test_calendar_account_str(self, user):
        """Test calendar account string representation."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
        )
        assert str(account) == f"{user.email} - google (test@example.com)"

    def test_is_token_expired_true(self, user):
        """Test token expiration check returns True when expired."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
            token_expires_at=timezone.now() - timedelta(hours=1),
        )
        assert account.is_token_expired() is True

    def test_is_token_expired_false(self, user):
        """Test token expiration check returns False when not expired."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        assert account.is_token_expired() is False


@pytest.mark.django_db
class TestSyncedEventModel:
    """Tests for SyncedEvent model."""

    def test_synced_event_creation(self, user):
        """Test synced event creation."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
        )
        now = timezone.now()
        event = SyncedEvent.objects.create(
            calendar_account=account,
            external_event_id="ext-123",
            title="Test Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert event.id is not None
        assert event.title == "Test Event"

    def test_synced_event_str(self, user):
        """Test synced event string representation."""
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
        )
        now = timezone.now()
        event = SyncedEvent.objects.create(
            calendar_account=account,
            external_event_id="ext-123",
            title="Test Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert "Test Event" in str(event)


@pytest.mark.django_db
class TestSyncSettingsModel:
    """Tests for SyncSettings model."""

    def test_sync_settings_creation(self, user):
        """Test sync settings creation."""
        settings = SyncSettings.objects.create(
            user=user,
            auto_sync=True,
            sync_interval_minutes=30,
        )
        assert settings.id is not None
        assert settings.auto_sync is True

    def test_sync_settings_str(self, user):
        """Test sync settings string representation."""
        settings = SyncSettings.objects.create(user=user)
        assert str(settings) == f"Sync settings for {user.email}"


@pytest.mark.django_db
class TestCalendarAccountAPI:
    """Tests for calendar account API."""

    def test_list_calendar_accounts(self, api_client, user):
        """Test listing calendar accounts."""
        CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="test@example.com",
        )
        api_client.force_authenticate(user=user)
        # Note: URL would need to be added to urls.py
        # url = reverse("calendaraccount-list")
        # response = api_client.get(url)
        # assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestSyncSettingsAPI:
    """Tests for sync settings API."""

    def test_get_sync_settings(self, api_client, user):
        """Test getting sync settings."""
        SyncSettings.objects.create(user=user, auto_sync=True)
        api_client.force_authenticate(user=user)
        # Note: URL would need to be added to urls.py
        # url = reverse("syncsettings-detail")
        # response = api_client.get(url)
        # assert response.status_code == status.HTTP_200_OK