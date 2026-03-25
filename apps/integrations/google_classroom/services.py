"""
Services for Google Classroom API integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .models import (
    GoogleClassroomAccount,
    SyncState,
    SyncedAnnouncement,
    SyncedAssignment,
    SyncedCourse,
    SyncedSubmission,
)

logger = logging.getLogger(__name__)


# Google OAuth2 and API constants
GOOGLE_OAUTH2_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CLASSROOM_API_BASE = "https://classroom.googleapis.com/v1"

# Required Google Classroom API scopes
GOOGLE_CLASSROOM_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleClassroomOAuthService:
    """Service for handling Google OAuth2 flow."""

    @staticmethod
    def _get_client_id() -> str:
        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or getattr(
            settings, "GOOGLE_CLIENT_ID", ""
        )
        if not client_id:
            raise ImproperlyConfigured(
                "Google Classroom OAuth client ID is not configured."
            )
        return client_id

    @staticmethod
    def _get_client_secret() -> str:
        client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or getattr(
            settings, "GOOGLE_CLIENT_SECRET", ""
        )
        if not client_secret:
            raise ImproperlyConfigured(
                "Google Classroom OAuth client secret is not configured."
            )
        return client_secret

    @staticmethod
    def get_authorization_url(redirect_uri: str, state: str = "") -> str:
        """Generate the OAuth2 authorization URL."""
        params = {
            "client_id": GoogleClassroomOAuthService._get_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_CLASSROOM_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        from urllib.parse import urlencode
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        data = {
            "client_id": GoogleClassroomOAuthService._get_client_id(),
            "client_secret": GoogleClassroomOAuthService._get_client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        response = requests.post(GOOGLE_OAUTH2_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """Refresh an expired access token."""
        data = {
            "client_id": GoogleClassroomOAuthService._get_client_id(),
            "client_secret": GoogleClassroomOAuthService._get_client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(GOOGLE_OAUTH2_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_user_info(access_token: str) -> dict:
        """Get user info from Google API."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        response.raise_for_status()
        return response.json()


class GoogleClassroomAPIService:
    """Service for interacting with Google Classroom API."""

    def __init__(self, account: GoogleClassroomAccount):
        self.account = account

    def _ensure_valid_token(self) -> str:
        """Ensure the access token is valid, refreshing if necessary."""
        if self.account.token_expires_at <= timezone.now():
            tokens = GoogleClassroomOAuthService.refresh_access_token(
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
        """Make an authenticated request to the Google Classroom API."""
        token = self._ensure_valid_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        url = f"{GOOGLE_CLASSROOM_API_BASE}{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            # Token might have been revoked, try refreshing
            token = self._ensure_valid_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(method, url, headers=headers, **kwargs)

        response.raise_for_status()
        return response.json()

    def get_courses(self, page_token: Optional[str] = None) -> dict:
        """Get list of courses from Google Classroom."""
        params = {}
        if page_token:
            params["pageToken"] = page_token

        return self._make_request("GET", "/courses", params=params)

    def get_course(self, course_id: str) -> dict:
        """Get a specific course from Google Classroom."""
        return self._make_request("GET", f"/courses/{course_id}")

    def get_coursework(self, course_id: str, page_token: Optional[str] = None) -> dict:
        """Get coursework (assignments) for a course."""
        params = {}
        if page_token:
            params["pageToken"] = page_token

        return self._make_request("GET", f"/courses/{course_id}/courseWork", params=params)

    def get_coursework_details(self, course_id: str, coursework_id: str) -> dict:
        """Get details of a specific coursework."""
        return self._make_request("GET", f"/courses/{course_id}/courseWork/{coursework_id}")

    def get_student_submissions(
        self, course_id: str, course_work_id: str, page_token: Optional[str] = None
    ) -> dict:
        """Get student submissions for a coursework."""
        params = {}
        if page_token:
            params["pageToken"] = page_token

        return self._make_request(
            "GET",
            f"/courses/{course_id}/courseWork/{course_work_id}/studentSubmissions",
            params=params,
        )

    def get_announcements(self, course_id: str, page_token: Optional[str] = None) -> dict:
        """Get announcements for a course."""
        params = {}
        if page_token:
            params["pageToken"] = page_token

        return self._make_request("GET", f"/courses/{course_id}/announcements", params=params)


class GoogleClassroomSyncService:
    """Service for syncing data from Google Classroom."""

    def __init__(self, account: GoogleClassroomAccount):
        self.account = account
        self.api_service = GoogleClassroomAPIService(account)

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
            self.account.sync_status = GoogleClassroomAccount.SyncStatus.SYNCING
            self.account.save(update_fields=["sync_status"])

            courses_count = self._sync_courses()
            assignments_count = self._sync_assignments()
            announcements_count = self._sync_announcements()
            submissions_count = self._sync_submissions()

            # Update sync state with results
            sync_state.result = SyncState.SyncResult.SUCCESS
            sync_state.completed_at = timezone.now()
            sync_state.courses_count = courses_count
            sync_state.assignments_count = assignments_count
            sync_state.announcements_count = announcements_count
            sync_state.submissions_count = submissions_count
            sync_state.save()

            # Update account status
            self.account.sync_status = GoogleClassroomAccount.SyncStatus.ACTIVE
            self.account.last_sync_at = timezone.now()
            self.account.last_error = ""
            self.account.save(update_fields=["sync_status", "last_sync_at", "last_error"])

        except Exception as e:
            logger.exception("Error syncing Google Classroom data")
            sync_state.result = SyncState.SyncResult.FAILED
            sync_state.completed_at = timezone.now()
            sync_state.errors = str(e)
            sync_state.save()

            self.account.sync_status = GoogleClassroomAccount.SyncStatus.ERROR
            self.account.last_error = str(e)
            self.account.save(update_fields=["sync_status", "last_error"])

        return sync_state

    def _sync_courses(self) -> int:
        """Sync courses from Google Classroom."""
        courses_synced = 0
        page_token = None

        while True:
            response = self.api_service.get_courses(page_token)
            courses = response.get("courses", [])

            for course_data in courses:
                # Only process courses where user is a teacher or student
                if course_data.get("courseState") not in ["ACTIVE", "ARCHIVED"]:
                    continue

                synced_course, created = SyncedCourse.objects.update_or_create(
                    google_course_id=course_data["id"],
                    account=self.account,
                    defaults={
                        "name": course_data.get("name", ""),
                        "section": course_data.get("section", ""),
                        "description": course_data.get("description", ""),
                        "room": course_data.get("room", ""),
                        "owner_id": course_data.get("ownerId", ""),
                        "enrollment_code": course_data.get("enrollmentCode", ""),
                        "last_synced_at": timezone.now(),
                    },
                )
                courses_synced += 1

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return courses_synced

    def _sync_assignments(self) -> int:
        """Sync assignments/coursework from Google Classroom."""
        assignments_synced = 0
        synced_courses = SyncedCourse.objects.filter(account=self.account)

        for synced_course in synced_courses:
            page_token = None

            while True:
                response = self.api_service.get_coursework(
                    synced_course.google_course_id, page_token
                )
                coursework_list = response.get("courseWork", [])

                for coursework_data in coursework_list:
                    # Parse due date if present
                    due_date = None
                    if coursework_data.get("dueDate") and coursework_data.get("dueTime"):
                        due_date = timezone.make_aware(
                            datetime(
                                coursework_data["dueDate"]["year"],
                                coursework_data["dueDate"]["month"],
                                coursework_data["dueDate"]["day"],
                                coursework_data["dueTime"]["hours"],
                                coursework_data["dueTime"]["minutes"],
                            )
                        )

                    SyncedAssignment.objects.update_or_create(
                        google_assignment_id=coursework_data["id"],
                        synced_course=synced_course,
                        defaults={
                            "title": coursework_data.get("title", ""),
                            "description": coursework_data.get("description", ""),
                            "state": coursework_data.get("state", "PUBLISHED"),
                            "due_date": due_date,
                            "max_points": coursework_data.get("maxPoints"),
                            "work_type": coursework_data.get("workType", ""),
                            "alternate_link": coursework_data.get("alternateLink", ""),
                            "last_synced_at": timezone.now(),
                        },
                    )
                    assignments_synced += 1

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        return assignments_synced

    def _sync_announcements(self) -> int:
        """Sync announcements from Google Classroom."""
        announcements_synced = 0
        synced_courses = SyncedCourse.objects.filter(account=self.account)

        for synced_course in synced_courses:
            page_token = None

            while True:
                response = self.api_service.get_announcements(
                    synced_course.google_course_id, page_token
                )
                announcements = response.get("announcements", [])

                for announcement_data in announcements:
                    # Parse scheduled date
                    scheduled_date = None
                    if announcement_data.get("scheduledTime"):
                        scheduled_date = datetime.fromisoformat(
                            announcement_data["scheduledTime"].replace("Z", "+00:00")
                        )
                        scheduled_date = timezone.make_aware(scheduled_date) if scheduled_date.tzinfo is None else scheduled_date

                    SyncedAnnouncement.objects.update_or_create(
                        google_announcement_id=announcement_data["id"],
                        synced_course=synced_course,
                        defaults={
                            "text": announcement_data.get("text", ""),
                            "state": announcement_data.get("state", "PUBLISHED"),
                            "scheduled_date": scheduled_date,
                            "alternate_link": announcement_data.get("alternateLink", ""),
                            "last_synced_at": timezone.now(),
                        },
                    )
                    announcements_synced += 1

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        return announcements_synced

    def _sync_submissions(self) -> int:
        """Sync student submissions from Google Classroom."""
        submissions_synced = 0
        synced_assignments = SyncedAssignment.objects.filter(
            synced_course__account=self.account
        )

        for synced_assignment in synced_assignments:
            page_token = None

            while True:
                response = self.api_service.get_student_submissions(
                    synced_assignment.synced_course.google_course_id,
                    synced_assignment.google_assignment_id,
                    page_token,
                )
                submissions = response.get("studentSubmissions", [])

                for submission_data in submissions:
                    # Parse submitted time
                    submitted_at = None
                    if submission_data.get("submittedAt"):
                        submitted_at = datetime.fromisoformat(
                            submission_data["submittedAt"].replace("Z", "+00:00")
                        )
                        submitted_at = timezone.make_aware(submitted_at) if submitted_at.tzinfo is None else submitted_at

                    # Parse returned time
                    returned_at = None
                    if submission_data.get("returnedAt"):
                        returned_at = datetime.fromisoformat(
                            submission_data["returnedAt"].replace("Z", "+00:00")
                        )
                        returned_at = timezone.make_aware(returned_at) if returned_at.tzinfo is None else returned_at

                    SyncedSubmission.objects.update_or_create(
                        google_submission_id=submission_data["id"],
                        synced_assignment=synced_assignment,
                        defaults={
                            "student_email": submission_data.get("userId", ""),
                            "state": submission_data.get("state", "CREATED"),
                            "assigned_grade": submission_data.get("assignedGrade"),
                            "draft_grade": submission_data.get("draftGrade"),
                            "submitted_at": submitted_at,
                            "returned_at": returned_at,
                            "last_synced_at": timezone.now(),
                        },
                    )
                    submissions_synced += 1

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        return submissions_synced
