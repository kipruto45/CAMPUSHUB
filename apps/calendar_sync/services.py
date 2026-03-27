"""
Services for Calendar Sync.
"""

import logging
from datetime import datetime, time, timedelta, timezone as dt_timezone
from typing import List
from urllib.parse import quote, urlencode

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import CalendarAccount, SyncedEvent, SyncSettings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 20
GOOGLE_OAUTH2_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
MICROSOFT_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
MICROSOFT_CALENDAR_SCOPES = [
    "offline_access",
    "User.Read",
    "Calendars.ReadWrite",
]


def _token_expiry_from_payload(payload: dict) -> timezone.datetime:
    return timezone.now() + timedelta(seconds=int(payload.get("expires_in", 3600) or 3600))


def _safe_json(response: requests.Response) -> dict:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        payload = _safe_json(response)
        message = (
            payload.get("error_description")
            or payload.get("error")
            or payload.get("message")
            or payload.get("error", {}).get("message")
            or response.text
            or str(exc)
        )
        raise requests.HTTPError(message, response=response) from exc


def _google_client_id() -> str:
    return str(getattr(settings, "GOOGLE_CLIENT_ID", "") or "").strip()


def _google_client_secret() -> str:
    return str(getattr(settings, "GOOGLE_CLIENT_SECRET", "") or "").strip()


def _google_redirect_uri() -> str:
    return str(
        getattr(settings, "GOOGLE_REDIRECT_URI", "")
        or getattr(settings, "SOCIAL_AUTH_GOOGLE_REDIRECT_URI", "")
        or ""
    ).strip()


def _microsoft_tenant() -> str:
    return str(getattr(settings, "MICROSOFT_TENANT_ID", "common") or "common").strip() or "common"


def _microsoft_client_id() -> str:
    return str(getattr(settings, "MICROSOFT_CLIENT_ID", "") or "").strip()


def _microsoft_client_secret() -> str:
    return str(getattr(settings, "MICROSOFT_CLIENT_SECRET", "") or "").strip()


def _microsoft_redirect_uri() -> str:
    return str(
        getattr(settings, "MICROSOFT_REDIRECT_URI", "")
        or getattr(settings, "SOCIAL_AUTH_MICROSOFT_REDIRECT_URI", "")
        or ""
    ).strip()


def _microsoft_token_url() -> str:
    tenant = _microsoft_tenant()
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def _normalize_redirect_uri(provider: str, redirect_uri: str = "") -> str:
    provided = str(redirect_uri or "").strip()
    if provided:
        return provided
    if provider == "google":
        return _google_redirect_uri()
    if provider == "outlook":
        return _microsoft_redirect_uri()
    return ""


def _parse_event_datetime(raw_value, all_day: bool = False):
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("dateTime") or raw_value.get("date")

    if not raw_value:
        return None

    raw_str = str(raw_value).strip()
    parsed = parse_datetime(raw_str)
    if parsed is not None:
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, dt_timezone.utc)
        return parsed

    parsed_date = parse_date(raw_str)
    if parsed_date is not None:
        default_time = time.min if all_day else time.min
        return timezone.make_aware(datetime.combine(parsed_date, default_time), dt_timezone.utc)

    try:
        parsed = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


class GoogleCalendarOAuthService:
    """Handle Google OAuth for calendar sync."""

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = "") -> str:
        params = {
            "client_id": _google_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        if state:
            params["state"] = state
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
        response = requests.post(
            GOOGLE_OAUTH2_TOKEN_URL,
            data={
                "client_id": _google_client_id(),
                "client_secret": _google_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        response = requests.post(
            GOOGLE_OAUTH2_TOKEN_URL,
            data={
                "client_id": _google_client_id(),
                "client_secret": _google_client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)

    @staticmethod
    def get_user_info(access_token: str) -> dict:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)


class OutlookCalendarOAuthService:
    """Handle Microsoft OAuth for Outlook calendar sync."""

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = "") -> str:
        params = {
            "client_id": _microsoft_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_CALENDAR_SCOPES),
        }
        if state:
            params["state"] = state

        tenant = _microsoft_tenant()
        return (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?"
            f"{urlencode(params)}"
        )

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
        response = requests.post(
            _microsoft_token_url(),
            data={
                "client_id": _microsoft_client_id(),
                "client_secret": _microsoft_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(MICROSOFT_CALENDAR_SCOPES),
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        response = requests.post(
            _microsoft_token_url(),
            data={
                "client_id": _microsoft_client_id(),
                "client_secret": _microsoft_client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(MICROSOFT_CALENDAR_SCOPES),
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)

    @staticmethod
    def get_user_info(access_token: str) -> dict:
        response = requests.get(
            f"{MICROSOFT_GRAPH_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        return _safe_json(response)


def get_calendar_oauth_service(provider: str):
    if provider == "google":
        return GoogleCalendarOAuthService
    if provider == "outlook":
        return OutlookCalendarOAuthService
    raise ValueError(f"Unsupported provider: {provider}")


def exchange_calendar_code(provider: str, code: str, redirect_uri: str = "") -> dict:
    service = get_calendar_oauth_service(provider)
    resolved_redirect_uri = _normalize_redirect_uri(provider, redirect_uri)
    if not resolved_redirect_uri:
        raise ValueError(f"{provider.title()} redirect URI is not configured")

    tokens = service.exchange_code_for_tokens(code, resolved_redirect_uri)
    access_token = str(tokens.get("access_token") or "").strip()
    if not access_token:
        raise ValueError(f"{provider.title()} did not return an access token")

    user_info = service.get_user_info(access_token)
    return {
        "tokens": tokens,
        "user_info": user_info,
        "redirect_uri": resolved_redirect_uri,
    }


class BaseCalendarService:
    """Base class for provider-specific calendar services."""

    def __init__(self, account: CalendarAccount):
        self.account = account
        self.provider = account.provider

    def _refresh_access_token(self, refresh_token: str) -> dict:
        raise NotImplementedError

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        raise NotImplementedError

    def refresh_token_if_needed(self) -> bool:
        """Refresh the OAuth token if expired."""
        if self.account.access_token and not self.account.is_token_expired():
            return True

        refresh_token = str(self.account.refresh_token or "").strip()
        if not refresh_token:
            return False

        try:
            tokens = self._refresh_access_token(refresh_token)
        except requests.RequestException:
            logger.exception(
                "Calendar token refresh failed for account_id=%s provider=%s",
                self.account.pk,
                self.provider,
            )
            return False

        access_token = str(tokens.get("access_token") or "").strip()
        if not access_token:
            return False

        self.account.access_token = access_token
        if tokens.get("refresh_token"):
            self.account.refresh_token = tokens["refresh_token"]
        self.account.token_expires_at = _token_expiry_from_payload(tokens)
        self.account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        return True

    def get_events(self, start_date, end_date) -> List[dict]:
        """Fetch events from the external calendar."""
        raise NotImplementedError

    def create_event(self, event_data: dict) -> dict:
        """Create an event in the external calendar."""
        raise NotImplementedError

    def update_event(self, event_id: str, event_data: dict) -> dict:
        """Update an event in the external calendar."""
        raise NotImplementedError

    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the external calendar."""
        raise NotImplementedError


class GoogleCalendarService(BaseCalendarService):
    """Google Calendar API service."""

    def _calendar_id(self) -> str:
        return quote(str(self.account.calendar_id or "primary").strip() or "primary", safe="")

    def _refresh_access_token(self, refresh_token: str) -> dict:
        return GoogleCalendarOAuthService.refresh_access_token(refresh_token)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        if not self.refresh_token_if_needed():
            raise ValueError("Token refresh failed")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.account.access_token}"

        response = requests.request(
            method,
            f"{GOOGLE_CALENDAR_API_BASE}{endpoint}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )

        if response.status_code == 401 and self.account.refresh_token:
            tokens = self._refresh_access_token(self.account.refresh_token)
            self.account.access_token = tokens["access_token"]
            if tokens.get("refresh_token"):
                self.account.refresh_token = tokens["refresh_token"]
            self.account.token_expires_at = _token_expiry_from_payload(tokens)
            self.account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
            headers["Authorization"] = f"Bearer {self.account.access_token}"
            response = requests.request(
                method,
                f"{GOOGLE_CALENDAR_API_BASE}{endpoint}",
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )

        _raise_for_status(response)
        return _safe_json(response)

    def get_events(self, start_date, end_date) -> List[dict]:
        response = self._make_request(
            "GET",
            f"/calendars/{self._calendar_id()}/events",
            params={
                "timeMin": start_date.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
                "timeMax": end_date.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        return response.get("items", [])

    def create_event(self, event_data: dict) -> dict:
        return self._make_request(
            "POST",
            f"/calendars/{self._calendar_id()}/events",
            json=event_data,
        )

    def update_event(self, event_id: str, event_data: dict) -> dict:
        return self._make_request(
            "PATCH",
            f"/calendars/{self._calendar_id()}/events/{quote(event_id, safe='')}",
            json=event_data,
        )

    def delete_event(self, event_id: str) -> bool:
        self._make_request(
            "DELETE",
            f"/calendars/{self._calendar_id()}/events/{quote(event_id, safe='')}",
        )
        return True


class OutlookCalendarService(BaseCalendarService):
    """Microsoft Graph API service for Outlook Calendar."""

    def _refresh_access_token(self, refresh_token: str) -> dict:
        return OutlookCalendarOAuthService.refresh_access_token(refresh_token)

    def _calendar_endpoint(self, default_path: str) -> str:
        calendar_id = str(self.account.calendar_id or "").strip()
        if not calendar_id or calendar_id == "primary":
            return f"/me/{default_path}"
        return f"/me/calendars/{quote(calendar_id, safe='')}/{default_path}"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        if not self.refresh_token_if_needed():
            raise ValueError("Token refresh failed")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.account.access_token}"

        response = requests.request(
            method,
            f"{MICROSOFT_GRAPH_API_BASE}{endpoint}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )

        if response.status_code == 401 and self.account.refresh_token:
            tokens = self._refresh_access_token(self.account.refresh_token)
            self.account.access_token = tokens["access_token"]
            if tokens.get("refresh_token"):
                self.account.refresh_token = tokens["refresh_token"]
            self.account.token_expires_at = _token_expiry_from_payload(tokens)
            self.account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
            headers["Authorization"] = f"Bearer {self.account.access_token}"
            response = requests.request(
                method,
                f"{MICROSOFT_GRAPH_API_BASE}{endpoint}",
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )

        _raise_for_status(response)
        return _safe_json(response)

    def get_events(self, start_date, end_date) -> List[dict]:
        response = self._make_request(
            "GET",
            self._calendar_endpoint("calendarView"),
            params={
                "startDateTime": start_date.astimezone(dt_timezone.utc).isoformat(),
                "endDateTime": end_date.astimezone(dt_timezone.utc).isoformat(),
                "$top": 250,
            },
        )
        return response.get("value", [])

    def create_event(self, event_data: dict) -> dict:
        return self._make_request(
            "POST",
            self._calendar_endpoint("events"),
            json=event_data,
        )

    def update_event(self, event_id: str, event_data: dict) -> dict:
        return self._make_request(
            "PATCH",
            f"{self._calendar_endpoint('events')}/{quote(event_id, safe='')}",
            json=event_data,
        )

    def delete_event(self, event_id: str) -> bool:
        self._make_request(
            "DELETE",
            f"{self._calendar_endpoint('events')}/{quote(event_id, safe='')}",
        )
        return True


class CalendarSyncService:
    """Main service for syncing calendars."""

    @staticmethod
    def get_service(account: CalendarAccount) -> BaseCalendarService:
        """Get the appropriate calendar service for the account."""
        if account.provider == "google":
            return GoogleCalendarService(account)
        if account.provider == "outlook":
            return OutlookCalendarService(account)
        raise ValueError(f"Unsupported provider: {account.provider}")

    @staticmethod
    def _normalize_event_for_storage(account: CalendarAccount, event_data: dict) -> dict:
        if account.provider == "google":
            start_raw = event_data.get("start", {})
            end_raw = event_data.get("end", {})
            is_all_day = bool(start_raw.get("date")) and not start_raw.get("dateTime")
            return {
                "title": event_data.get("summary", ""),
                "description": event_data.get("description", ""),
                "start_time": _parse_event_datetime(start_raw, all_day=is_all_day),
                "end_time": _parse_event_datetime(end_raw, all_day=is_all_day),
                "location": event_data.get("location", ""),
                "is_all_day": is_all_day,
                "attendees": event_data.get("attendees", []),
            }

        start_raw = event_data.get("start", {})
        end_raw = event_data.get("end", {})
        return {
            "title": event_data.get("subject", ""),
            "description": event_data.get("bodyPreview")
            or event_data.get("body", {}).get("content", ""),
            "start_time": _parse_event_datetime(start_raw.get("dateTime"), all_day=event_data.get("isAllDay", False)),
            "end_time": _parse_event_datetime(end_raw.get("dateTime"), all_day=event_data.get("isAllDay", False)),
            "location": event_data.get("location", {}).get("displayName", ""),
            "is_all_day": bool(event_data.get("isAllDay", False)),
            "attendees": event_data.get("attendees", []),
        }

    @staticmethod
    def sync_calendar(account: CalendarAccount, days_ahead: int = 30) -> dict:
        """Sync events from external calendar to CampusHub."""
        service = CalendarSyncService.get_service(account)

        if not account.sync_enabled:
            return {"synced": 0, "errors": 0}

        start_date = timezone.now()
        end_date = start_date + timedelta(days=days_ahead)

        try:
            events = service.get_events(start_date, end_date)
            synced_count = 0
            error_count = 0

            for event_data in events:
                try:
                    defaults = CalendarSyncService._normalize_event_for_storage(account, event_data)
                    if not defaults["start_time"] or not defaults["end_time"]:
                        raise ValueError("Event is missing a valid start or end time")

                    SyncedEvent.objects.update_or_create(
                        calendar_account=account,
                        external_event_id=str(event_data.get("id", "") or ""),
                        defaults=defaults,
                    )
                    synced_count += 1
                except Exception:
                    logger.exception(
                        "Failed to sync event for account_id=%s provider=%s",
                        account.pk,
                        account.provider,
                    )
                    error_count += 1

            account.last_sync_at = timezone.now()
            account.save(update_fields=["last_sync_at", "updated_at"])

            return {
                "synced": synced_count,
                "errors": error_count,
                "total": len(events),
            }
        except Exception as exc:
            logger.exception(
                "Calendar sync failed for account_id=%s provider=%s",
                account.pk,
                account.provider,
            )
            return {"synced": 0, "errors": 1, "error": str(exc)}

    @staticmethod
    def push_campus_event_to_calendar(account: CalendarAccount, campus_event) -> dict:
        """Push a CampusHub event to the external calendar."""
        service = CalendarSyncService.get_service(account)
        start_time = campus_event.start_time.astimezone(dt_timezone.utc)
        end_time = campus_event.end_time.astimezone(dt_timezone.utc)

        if account.provider == "google":
            event_data = {
                "summary": campus_event.title,
                "description": campus_event.description or "",
                "start": {
                    "dateTime": start_time.isoformat().replace("+00:00", "Z"),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time.isoformat().replace("+00:00", "Z"),
                    "timeZone": "UTC",
                },
                "location": campus_event.location or "",
            }
        else:
            event_data = {
                "subject": campus_event.title,
                "body": {
                    "contentType": "text",
                    "content": campus_event.description or "",
                },
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                },
                "location": {
                    "displayName": campus_event.location or "",
                },
            }

        try:
            result = service.create_event(event_data)
            return {"success": True, "external_id": result.get("id")}
        except Exception as exc:
            logger.exception(
                "Failed to push CampusHub event to external calendar for account_id=%s provider=%s",
                account.pk,
                account.provider,
            )
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_or_create_settings(user) -> SyncSettings:
        """Get or create sync settings for a user."""
        settings_obj, _created = SyncSettings.objects.get_or_create(user=user)
        return settings_obj

    @staticmethod
    def get_user_calendar_events(user, days_ahead: int = 30) -> List[SyncedEvent]:
        """Get all synced events for a user."""
        accounts = CalendarAccount.objects.filter(
            user=user,
            is_active=True,
            sync_enabled=True,
        )

        start_date = timezone.now()
        end_date = start_date + timedelta(days=days_ahead)

        return SyncedEvent.objects.filter(
            calendar_account__in=accounts,
            start_time__gte=start_date,
            start_time__lte=end_date,
            is_deleted=False,
        ).order_by("start_time")
