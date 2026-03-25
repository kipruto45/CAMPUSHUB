"""
Services for Microsoft Graph API integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from .models import (
    MicrosoftTeamsAccount,
    SyncState,
    SyncedAnnouncement,
    SyncedAssignment,
    SyncedChannel,
    SyncedSubmission,
    SyncedTeam,
)

logger = logging.getLogger(__name__)


# Microsoft OAuth2 and Graph API constants
MICROSOFT_OAUTH2_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Required Microsoft Graph API scopes for Teams
MICROSOFT_TEAMS_SCOPES = [
    "User.Read",
    "User.ReadBasic.All",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Read.All",
    "EducationAssignment.ReadWrite",
    "EducationSubmission.ReadWrite",
    "Calendars.Read",
    "OnlineMeetings.ReadWrite",
]

# Microsoft Teams API scopes (delegated)
TEAMS_SCOPES = [
    "https://graph.microsoft.com/.default",
    "User.Read",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "EducationAssignment.ReadWrite",
    "EducationSubmission.ReadWrite",
]


class MicrosoftTeamsOAuthService:
    """Service for handling Microsoft OAuth2 flow."""

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = "") -> str:
        """Generate the OAuth2 authorization URL."""
        params = {
            "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(TEAMS_SCOPES),
            "response_mode": "query",
        }
        if state:
            params["state"] = state

        from urllib.parse import urlencode
        return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        data = {
            "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
            "client_secret": settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(TEAMS_SCOPES),
        }

        response = requests.post(MICROSOFT_OAUTH2_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """Refresh an expired access token."""
        data = {
            "client_id": settings.MICROSOFT_OAUTH_CLIENT_ID,
            "client_secret": settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(TEAMS_SCOPES),
        }

        response = requests.post(MICROSOFT_OAUTH2_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_user_info(access_token: str) -> dict:
        """Get user info from Microsoft Graph API."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{MICROSOFT_GRAPH_API_BASE}/me",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


class MicrosoftTeamsAPIService:
    """Service for interacting with Microsoft Graph API."""

    def __init__(self, account: MicrosoftTeamsAccount):
        self.account = account

    def _ensure_valid_token(self) -> str:
        """Ensure the access token is valid, refreshing if necessary."""
        if self.account.token_expires_at <= timezone.now():
            tokens = MicrosoftTeamsOAuthService.refresh_access_token(
                self.account.refresh_token
            )
            self.account.access_token = tokens["access_token"]
            if "refresh_token" in tokens:
                self.account.refresh_token = tokens["refresh_token"]
            self.account.token_expires_at = timezone.now() + timedelta(
                seconds=tokens.get("expires_in", 3600)
            )
            self.account.save(update_fields=["access_token", "refresh_token", "token_expires_at"])

        return self.account.access_token

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to the Microsoft Graph API."""
        token = self._ensure_valid_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        url = f"{MICROSOFT_GRAPH_API_BASE}{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            # Token might have been revoked, try refreshing
            token = self._ensure_valid_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(method, url, headers=headers, **kwargs)

        response.raise_for_status()
        return response.json()

    def get_my_teams(self, page_token: Optional[str] = None) -> dict:
        """Get list of teams the user is a member of."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request("GET", "/me/joinedTeams", params=params)

    def get_team(self, team_id: str) -> dict:
        """Get a specific team."""
        return self._make_request("GET", f"/teams/{team_id}")

    def get_team_channels(self, team_id: str, page_token: Optional[str] = None) -> dict:
        """Get channels for a team."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request("GET", f"/teams/{team_id}/channels", params=params)

    def get_channel(self, team_id: str, channel_id: str) -> dict:
        """Get a specific channel."""
        return self._make_request("GET", f"/teams/{team_id}/channels/{channel_id}")

    def get_education_assignments(self, class_id: str, page_token: Optional[str] = None) -> dict:
        """Get assignments for an education class."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request(
            "GET",
            f"/education/classes/{class_id}/assignments",
            params=params,
        )

    def get_assignment(self, class_id: str, assignment_id: str) -> dict:
        """Get a specific assignment."""
        return self._make_request(
            "GET",
            f"/education/classes/{class_id}/assignments/{assignment_id}",
        )

    def get_assignment_submissions(
        self, class_id: str, assignment_id: str, page_token: Optional[str] = None
    ) -> dict:
        """Get submissions for an assignment."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request(
            "GET",
            f"/education/classes/{class_id}/assignments/{assignment_id}/submissions",
            params=params,
        )

    def get_channel_messages(self, team_id: str, channel_id: str, page_token: Optional[str] = None) -> dict:
        """Get messages from a channel."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request(
            "GET",
            f"/teams/{team_id}/channels/{channel_id}/messages",
            params=params,
        )

    def get_education_classes(self, page_token: Optional[str] = None) -> dict:
        """Get education classes the user is enrolled in."""
        params = {}
        if page_token:
            params["$skiptoken"] = page_token

        return self._make_request("GET", "/education/me/classes", params=params)

    def create_online_meeting(self, subject: str, start_time: datetime, end_time: datetime) -> dict:
        """Create an online meeting."""
        data = {
            "subject": subject,
            "startDateTime": start_time.isoformat(),
            "endDateTime": end_time.isoformat(),
        }
        return self._make_request("POST", "/me/onlineMeetings", json=data)


class MicrosoftTeamsSyncService:
    """Service for syncing data from Microsoft Teams."""

    def __init__(self, account: MicrosoftTeamsAccount):
        self.account = account
        self.api_service = MicrosoftTeamsAPIService(account)

    def sync_all(self, sync_type: str = SyncState.SyncType.FULL) -> SyncState:
        """Perform a full or incremental sync."""
        # Create sync state record
        sync_state = SyncState.objects.create(
            account=self.account,
            sync_type=sync_type,
            result=SyncState.SyncResult.PENDING,
            started_at=timezone.now(),
        )

        try:
            # Update account status to syncing
            self.account.sync_status = MicrosoftTeamsAccount.SyncStatus.SYNCING
            self.account.save(update_fields=["sync_status"])

            teams_count = self._sync_teams()
            channels_count = self._sync_channels()
            assignments_count = self._sync_assignments()
            announcements_count = self._sync_announcements()
            submissions_count = self._sync_submissions()

            # Update sync state with results
            sync_state.result = SyncState.SyncResult.SUCCESS
            sync_state.completed_at = timezone.now()
            sync_state.teams_count = teams_count
            sync_state.channels_count = channels_count
            sync_state.assignments_count = assignments_count
            sync_state.announcements_count = announcements_count
            sync_state.submissions_count = submissions_count
            sync_state.save()

            # Update account status
            self.account.sync_status = MicrosoftTeamsAccount.SyncStatus.ACTIVE
            self.account.last_sync_at = timezone.now()
            self.account.last_error = ""
            self.account.save(update_fields=["sync_status", "last_sync_at", "last_error"])

        except Exception as e:
            logger.exception("Error syncing Microsoft Teams data")
            sync_state.result = SyncState.SyncResult.FAILED
            sync_state.completed_at = timezone.now()
            sync_state.errors = str(e)
            sync_state.save()

            self.account.sync_status = MicrosoftTeamsAccount.SyncStatus.ERROR
            self.account.last_error = str(e)
            self.account.save(update_fields=["sync_status", "last_error"])

        return sync_state

    def _sync_teams(self) -> int:
        """Sync teams from Microsoft Teams."""
        teams_synced = 0
        page_token = None

        while True:
            response = self.api_service.get_my_teams(page_token)
            teams = response.get("value", [])

            for team_data in teams:
                synced_team, created = SyncedTeam.objects.update_or_create(
                    team_id=team_data.get("id", ""),
                    account=self.account,
                    defaults={
                        "display_name": team_data.get("displayName", ""),
                        "description": team_data.get("description", ""),
                        "visibility": team_data.get("visibility", "Private"),
                        "last_synced_at": timezone.now(),
                    },
                )
                teams_synced += 1

            page_token = response.get("@odata.nextLink")
            if not page_token:
                break

        return teams_synced

    def _sync_channels(self) -> int:
        """Sync channels from Microsoft Teams."""
        channels_synced = 0
        synced_teams = SyncedTeam.objects.filter(account=self.account)

        for synced_team in synced_teams:
            page_token = None

            while True:
                response = self.api_service.get_team_channels(
                    synced_team.team_id, page_token
                )
                channels = response.get("value", [])

                for channel_data in channels:
                    SyncedChannel.objects.update_or_create(
                        channel_id=channel_data.get("id", ""),
                        synced_team=synced_team,
                        defaults={
                            "display_name": channel_data.get("displayName", ""),
                            "description": channel_data.get("description", ""),
                            "is_general": channel_data.get("isGeneral", False),
                            "web_url": channel_data.get("webUrl", ""),
                            "last_synced_at": timezone.now(),
                        },
                    )
                    channels_synced += 1

                page_token = response.get("@odata.nextLink")
                if not page_token:
                    break

        return channels_synced

    def _sync_assignments(self) -> int:
        """Sync assignments from Microsoft Teams."""
        assignments_synced = 0
        synced_teams = SyncedTeam.objects.filter(account=self.account)

        for synced_team in synced_teams:
            # Try to get education class assignments
            try:
                page_token = None

                while True:
                    response = self.api_service.get_education_classes(page_token)
                    classes = response.get("value", [])

                    for class_data in classes:
                        class_id = class_data.get("id")
                        if not class_id:
                            continue

                        # Get assignments for this class
                        try:
                            assignments_response = self.api_service.get_education_assignments(class_id)
                            assignments = assignments_response.get("value", [])

                            for assignment_data in assignments:
                                # Parse due date
                                due_date_time = None
                                if assignment_data.get("dueDateTime"):
                                    due_date_time = datetime.fromisoformat(
                                        assignment_data["dueDateTime"].replace("Z", "+00:00")
                                    )
                                    due_date_time = timezone.make_aware(due_date_time) if due_date_time.tzinfo is None else due_date_time

                                SyncedAssignment.objects.update_or_create(
                                    assignment_id=assignment_data.get("id", ""),
                                    synced_team=synced_team,
                                    defaults={
                                        "display_name": assignment_data.get("displayName", ""),
                                        "instructions": assignment_data.get("instructions", {}).get("text", "") if isinstance(assignment_data.get("instructions"), dict) else str(assignment_data.get("instructions", "")),
                                        "status": assignment_data.get("status", "Draft"),
                                        "due_date_time": due_date_time,
                                        "due_date_includes_time": assignment_data.get("dueDateTimeIncludesTime", True),
                                        "grading_type": assignment_data.get("grading", {}).get("@odata.type", "") if isinstance(assignment_data.get("grading"), dict) else "",
                                        "max_points": assignment_data.get("grading", {}).get("maxPoints") if isinstance(assignment_data.get("grading"), dict) else None,
                                        "web_url": assignment_data.get("webUrl", ""),
                                        "last_synced_at": timezone.now(),
                                    },
                                )
                                assignments_synced += 1
                        except Exception as e:
                            logger.warning(f"Error fetching assignments for class {class_id}: {e}")

                    page_token = response.get("@odata.nextLink")
                    if not page_token:
                        break
            except Exception as e:
                logger.warning(f"Error fetching education classes for team {synced_team.team_id}: {e}")

        return assignments_synced

    def _sync_announcements(self) -> int:
        """Sync announcements from Microsoft Teams channels."""
        announcements_synced = 0
        synced_channels = SyncedChannel.objects.filter(synced_team__account=self.account)

        for synced_channel in synced_channels:
            page_token = None

            while True:
                try:
                    response = self.api_service.get_channel_messages(
                        synced_channel.synced_team.team_id,
                        synced_channel.channel_id,
                        page_token,
                    )
                    messages = response.get("value", [])

                    for message_data in messages:
                        # Only sync messages that are announcements (check for isAnnounce or similar)
                        if message_data.get("isAnnounce", False) or message_data.get("summary"):
                            SyncedAnnouncement.objects.update_or_create(
                                announcement_id=message_data.get("id", ""),
                                synced_channel=synced_channel,
                                defaults={
                                    "topic": message_data.get("subject", "Announcement"),
                                    "summary": message_data.get("summary", ""),
                                    "body": message_data.get("body", {}).get("content", "") if isinstance(message_data.get("body"), dict) else str(message_data.get("body", "")),
                                    "is_pinned": message_data.get("isPinned", False),
                                    "web_url": message_data.get("webUrl", ""),
                                    "last_synced_at": timezone.now(),
                                },
                            )
                            announcements_synced += 1

                    page_token = response.get("@odata.nextLink")
                    if not page_token:
                        break
                except Exception as e:
                    logger.warning(f"Error fetching messages for channel {synced_channel.channel_id}: {e}")
                    break

        return announcements_synced

    def _sync_submissions(self) -> int:
        """Sync student submissions from Microsoft Teams."""
        submissions_synced = 0
        synced_assignments = SyncedAssignment.objects.filter(
            synced_team__account=self.account
        )

        for synced_assignment in synced_assignments:
            # We need the class ID to fetch submissions - this is stored in the team
            # For now, we'll skip submissions sync as it requires additional mapping
            # In a production implementation, you'd store the class ID in SyncedTeam
            pass

        return submissions_synced


class MicrosoftTeamsMeetingService:
    """Service for creating and managing Teams meetings."""

    def __init__(self, account: MicrosoftTeamsAccount):
        self.account = account
        self.api_service = MicrosoftTeamsAPIService(account)

    def create_meeting(
        self,
        subject: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Create a Teams meeting for a study session."""
        meeting = self.api_service.create_online_meeting(
            subject=subject,
            start_time=start_time,
            end_time=end_time,
        )
        return meeting

    def get_meeting_link(self, meeting_id: str) -> str:
        """Get the join URL for a meeting."""
        # Meeting creation returns the join URL directly
        return f"https://teams.microsoft.com/l/meetup-join/{meeting_id}"