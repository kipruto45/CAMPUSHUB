"""
Views for Google Classroom integration API.
"""

import uuid

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    GoogleClassroomAccount,
    SyncState,
    SyncedAssignment,
    SyncedCourse,
)
from .serializers import (
    GoogleClassroomAccountSerializer,
    GoogleClassroomConnectResponseSerializer,
    GoogleClassroomStatusSerializer,
    GoogleClassroomSyncResponseSerializer,
    SyncStateSerializer,
)
from .services import (
    GoogleClassroomOAuthService,
    GoogleClassroomSyncService,
)


def _build_google_classroom_redirect_uri(request) -> str:
    """Resolve the OAuth callback URI using settings or the active API prefix."""
    configured_redirect = getattr(settings, "GOOGLE_CLASSROOM_REDIRECT_URI", "").strip()
    if configured_redirect:
        return configured_redirect

    api_prefix = "/api/v1/" if request.path.startswith("/api/v1/") else "/api/"
    return request.build_absolute_uri(
        f"{api_prefix}integrations/google-classroom/oauth/callback/"
    )


class ConnectGoogleClassroomView(APIView):
    """View to initiate Google OAuth2 flow for Google Classroom."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Generate authorization URL and return it to the client."""
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        
        # Store state in session for callback verification
        request.session["google_classroom_oauth_state"] = state
        request.session["google_classroom_user_id"] = str(request.user.id)

        # Build redirect URI
        redirect_uri = _build_google_classroom_redirect_uri(request)

        # Generate authorization URL
        authorization_url = GoogleClassroomOAuthService.get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )

        serializer = GoogleClassroomConnectResponseSerializer(
            data={"authorization_url": authorization_url, "state": state}
        )
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class GoogleClassroomOAuthCallbackView(APIView):
    """View to handle OAuth2 callback from Google."""

    permission_classes = []  # No authentication required for OAuth callback

    def get(self, request):
        """Handle the OAuth callback and exchange code for tokens."""
        error = request.query_params.get("error")
        if error:
            return Response(
                {"error": error, "message": "Authorization failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            return Response(
                {"error": "Invalid request", "message": "Missing code or state"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify state
        stored_state = request.session.pop("google_classroom_oauth_state", None)
        if state != stored_state:
            return Response(
                {"error": "Invalid state", "message": "CSRF protection failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the user from session (we need to store user ID in session before redirect)
        user_id = request.session.get("google_classroom_user_id")
        if not user_id:
            return Response(
                {"error": "Session expired", "message": "Please try connecting again"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Exchange code for tokens
            tokens = GoogleClassroomOAuthService.exchange_code_for_tokens(
                code=code,
                redirect_uri=_build_google_classroom_redirect_uri(request),
            )

            # Get user info
            user_info = GoogleClassroomOAuthService.get_user_info(tokens["access_token"])

            # Calculate token expiry
            expires_in = tokens.get("expires_in", 3600)
            token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)

            # Create or update Google Classroom account
            account, created = GoogleClassroomAccount.objects.update_or_create(
                user=user,
                defaults={
                    "google_user_id": user_info["id"],
                    "email": user_info["email"],
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens.get("refresh_token", ""),
                    "token_expires_at": token_expires_at,
                    "sync_status": GoogleClassroomAccount.SyncStatus.ACTIVE,
                },
            )

            # Clean up session
            request.session.pop("google_classroom_user_id", None)

            return Response(
                {
                    "message": "Google Classroom connected successfully",
                    "account": GoogleClassroomAccountSerializer(account).data,
                },
                status=status.HTTP_200_OK if created else status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Token exchange failed", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DisconnectGoogleClassroomView(APIView):
    """View to disconnect Google Classroom integration."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Disconnect the user's Google Classroom account."""
        try:
            account = GoogleClassroomAccount.objects.get(user=request.user)
        except GoogleClassroomAccount.DoesNotExist:
            return Response(
                {"error": "No Google Classroom account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Delete the account (this will cascade to related models)
        account.delete()

        return Response(
            {"message": "Google Classroom disconnected successfully"},
            status=status.HTTP_200_OK,
        )


class GoogleClassroomStatusView(APIView):
    """View to get Google Classroom integration status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the current status of the Google Classroom integration."""
        try:
            account = GoogleClassroomAccount.objects.get(user=request.user)
        except GoogleClassroomAccount.DoesNotExist:
            return Response(
                {
                    "is_connected": False,
                    "synced_courses_count": 0,
                    "synced_assignments_count": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Get last sync
        last_sync = SyncState.objects.filter(account=account).first()

        # Get counts
        synced_courses_count = SyncedCourse.objects.filter(account=account).count()
        synced_assignments_count = SyncedAssignment.objects.filter(
            synced_course__account=account
        ).count()

        data = {
            "is_connected": True,
            "account": GoogleClassroomAccountSerializer(account).data,
            "last_sync": SyncStateSerializer(last_sync).data if last_sync else None,
            "synced_courses_count": synced_courses_count,
            "synced_assignments_count": synced_assignments_count,
        }

        serializer = GoogleClassroomStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GoogleClassroomSyncView(APIView):
    """View to trigger Google Classroom sync."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Trigger a manual sync of Google Classroom data."""
        try:
            account = GoogleClassroomAccount.objects.get(user=request.user)
        except GoogleClassroomAccount.DoesNotExist:
            return Response(
                {"error": "No Google Classroom account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Start sync in background (for production, use Celery)
        # For now, run synchronously
        sync_service = GoogleClassroomSyncService(account)
        sync_state = sync_service.sync_all(sync_type=SyncState.SyncType.MANUAL)

        return Response(
            {
                "sync_started": True,
                "sync_state": SyncStateSerializer(sync_state).data,
            },
            status=status.HTTP_200_OK,
        )


class GoogleClassroomCoursesView(APIView):
    """View to list synced courses."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_integrations_google_classroom_courses_list")
    def get(self, request):
        """Get all synced courses for the user."""
        try:
            account = GoogleClassroomAccount.objects.get(user=request.user)
        except GoogleClassroomAccount.DoesNotExist:
            return Response(
                {"error": "No Google Classroom account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        courses = SyncedCourse.objects.filter(account=account)
        from .serializers import SyncedCourseSerializer
        
        serializer = SyncedCourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GoogleClassroomCourseDetailView(APIView):
    """View to get course details with assignments and announcements."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_integrations_google_classroom_courses_retrieve")
    def get(self, request, course_id):
        """Get details of a specific synced course."""
        try:
            account = GoogleClassroomAccount.objects.get(user=request.user)
        except GoogleClassroomAccount.DoesNotExist:
            return Response(
                {"error": "No Google Classroom account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            course = SyncedCourse.objects.get(
                id=course_id,
                account=account,
            )
        except SyncedCourse.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .serializers import SyncedCourseSerializer, SyncedAssignmentSerializer, SyncedAnnouncementSerializer

        data = {
            "course": SyncedCourseSerializer(course).data,
            "assignments": SyncedAssignmentSerializer(
                course.synced_assignments.all(),
                many=True,
            ).data,
            "announcements": SyncedAnnouncementSerializer(
                course.synced_announcements.all(),
                many=True,
            ).data,
        }

        return Response(data, status=status.HTTP_200_OK)
