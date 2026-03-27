"""
Tests for calendar_sync app.
"""
import pytest
import requests
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.calendar_sync.models import CalendarAccount, SyncedEvent, SyncSettings
from apps.calendar_sync.services import CalendarSyncService

User = get_user_model()


GOOGLE_CONNECT_URL = "/api/v1/calendar-sync/connect/google/"
OUTLOOK_CONNECT_URL = "/api/v1/calendar-sync/connect/outlook/"
CALLBACK_URL = "/api/v1/calendar-sync/oauth/callback/"


class StubResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or ""
        self.content = b"" if payload is None and not text else (text or "json").encode()

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.text or f"HTTP {self.status_code}", response=self)


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

    def test_connect_google_returns_real_auth_url(self, api_client, user, settings):
        settings.GOOGLE_CLIENT_ID = "google-client-id"
        settings.GOOGLE_REDIRECT_URI = "campushub://calendar/google"
        api_client.force_authenticate(user=user)

        response = api_client.post(GOOGLE_CONNECT_URL, {}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["provider"] == "google"
        assert "accounts.google.com" in response.data["auth_url"]
        assert "calendar.events" in response.data["auth_url"]
        assert "campushub%3A%2F%2Fcalendar%2Fgoogle" in response.data["auth_url"]

    def test_connect_outlook_returns_real_auth_url(self, api_client, user, settings):
        settings.MICROSOFT_CLIENT_ID = "ms-client-id"
        settings.MICROSOFT_REDIRECT_URI = "campushub://calendar/outlook"
        settings.MICROSOFT_TENANT_ID = "common"
        api_client.force_authenticate(user=user)

        response = api_client.post(OUTLOOK_CONNECT_URL, {}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["provider"] == "outlook"
        assert "login.microsoftonline.com/common/oauth2/v2.0/authorize" in response.data["auth_url"]
        assert "Calendars.ReadWrite" in response.data["auth_url"]
        assert "campushub%3A%2F%2Fcalendar%2Foutlook" in response.data["auth_url"]

    @patch("apps.calendar_sync.services.requests.get")
    @patch("apps.calendar_sync.services.requests.post")
    def test_google_callback_exchanges_code_and_saves_account(
        self, mock_post, mock_get, api_client, user, settings
    ):
        settings.GOOGLE_CLIENT_ID = "google-client-id"
        settings.GOOGLE_CLIENT_SECRET = "google-client-secret"
        settings.GOOGLE_REDIRECT_URI = "campushub://calendar/google"
        api_client.force_authenticate(user=user)
        mock_post.return_value = StubResponse(
            payload={
                "access_token": "access-123",
                "refresh_token": "refresh-123",
                "expires_in": 3600,
            }
        )
        mock_get.return_value = StubResponse(
            payload={"email": "calendar-user@example.com"}
        )

        response = api_client.post(
            CALLBACK_URL,
            {
                "provider": "google",
                "code": "auth-code",
                "redirect_uri": "campushub://calendar/google",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        account = CalendarAccount.objects.get(user=user, provider="google")
        assert account.email == "calendar-user@example.com"
        assert account.access_token == "access-123"
        assert account.refresh_token == "refresh-123"

    @patch("apps.calendar_sync.services.requests.request")
    @patch("apps.calendar_sync.services.requests.post")
    def test_google_sync_refreshes_token_and_persists_events(
        self, mock_post, mock_request, user
    ):
        account = CalendarAccount.objects.create(
            user=user,
            provider="google",
            email="calendar-user@example.com",
            access_token="expired-access",
            refresh_token="refresh-123",
            token_expires_at=timezone.now() - timedelta(minutes=5),
            calendar_id="primary",
        )
        mock_post.return_value = StubResponse(
            payload={"access_token": "fresh-access", "expires_in": 3600}
        )
        mock_request.return_value = StubResponse(
            payload={
                "items": [
                    {
                        "id": "g-event-1",
                        "summary": "Google Event",
                        "description": "Imported from Google",
                        "start": {"dateTime": "2026-03-28T09:00:00Z"},
                        "end": {"dateTime": "2026-03-28T10:00:00Z"},
                        "location": "Room A",
                        "attendees": [{"email": "friend@example.com"}],
                    }
                ]
            }
        )

        result = CalendarSyncService.sync_calendar(account, days_ahead=7)

        account.refresh_from_db()
        synced_event = SyncedEvent.objects.get(calendar_account=account, external_event_id="g-event-1")
        assert result["synced"] == 1
        assert result["errors"] == 0
        assert account.access_token == "fresh-access"
        assert synced_event.title == "Google Event"
        assert synced_event.location == "Room A"

    @patch("apps.calendar_sync.services.requests.request")
    def test_outlook_sync_persists_graph_events(self, mock_request, user):
        account = CalendarAccount.objects.create(
            user=user,
            provider="outlook",
            email="outlook-user@example.com",
            access_token="active-access",
            refresh_token="refresh-123",
            token_expires_at=timezone.now() + timedelta(hours=1),
            calendar_id="primary",
        )
        mock_request.return_value = StubResponse(
            payload={
                "value": [
                    {
                        "id": "ms-event-1",
                        "subject": "Outlook Event",
                        "bodyPreview": "Imported from Outlook",
                        "start": {"dateTime": "2026-03-28T11:00:00+00:00"},
                        "end": {"dateTime": "2026-03-28T12:00:00+00:00"},
                        "location": {"displayName": "Library"},
                        "isAllDay": False,
                        "attendees": [
                            {
                                "emailAddress": {"address": "friend@example.com"},
                                "status": {"response": "accepted"},
                            }
                        ],
                    }
                ]
            }
        )

        result = CalendarSyncService.sync_calendar(account, days_ahead=7)

        synced_event = SyncedEvent.objects.get(calendar_account=account, external_event_id="ms-event-1")
        assert result["synced"] == 1
        assert result["errors"] == 0
        assert synced_event.title == "Outlook Event"
        assert synced_event.location == "Library"


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
