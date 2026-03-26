"""
Views for Microsoft Teams integration API.
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
    MicrosoftTeamsAccount,
    SyncState,
    SyncedAssignment,
    SyncedTeam,
)
from .serializers import (
    MicrosoftTeamsAccountSerializer,
    MicrosoftTeamsConnectResponseSerializer,
    MicrosoftTeamsStatusSerializer,
    MicrosoftTeamsSyncResponseSerializer,
    SyncStateSerializer,
)
from .services import (
    MicrosoftTeamsOAuthService,
    MicrosoftTeamsSyncService,
)


class ConnectMicrosoftTeamsView(APIView):
    """View to initiate Microsoft OAuth2 flow for Teams."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Generate authorization URL and return it to the client."""
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        
        # Store state in session for callback verification
        request.session["microsoft_teams_oauth_state"] = state
        # Store user ID in session for callback
        request.session["microsoft_teams_user_id"] = str(request.user.id)

        # Build redirect URI
        redirect_uri = request.build_absolute_uri("/api/integrations/microsoft-teams/oauth/callback/")

        # Generate authorization URL
        authorization_url = MicrosoftTeamsOAuthService.get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )

        serializer = MicrosoftTeamsConnectResponseSerializer(
            data={"authorization_url": authorization_url, "state": state}
        )
        serializer.is_valid()

        return Response(serializer.data, status=status.HTTP_200_OK)


class MicrosoftTeamsOAuthCallbackView(APIView):
    """View to handle OAuth2 callback from Microsoft."""

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
        stored_state = request.session.pop("microsoft_teams_oauth_state", None)
        if state != stored_state:
            return Response(
                {"error": "Invalid state", "message": "CSRF protection failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the user from session
        user_id = request.session.pop("microsoft_teams_user_id", None)
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
            tokens = MicrosoftTeamsOAuthService.exchange_code_for_tokens(
                code=code,
                redirect_uri=request.build_absolute_uri("/api/integrations/microsoft-teams/oauth/callback/"),
            )

            # Get user info
            user_info = MicrosoftTeamsOAuthService.get_user_info(tokens["access_token"])

            # Calculate token expiry
            expires_in = tokens.get("expires_in", 3600)
            token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)

            # Create or update Microsoft Teams account
            account, created = MicrosoftTeamsAccount.objects.update_or_create(
                user=user,
                defaults={
                    "microsoft_user_id": user_info.get("id", ""),
                    "email": user_info.get("mail", user_info.get("userPrincipalName", "")),
                    "display_name": user_info.get("displayName", ""),
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens.get("refresh_token", ""),
                    "token_expires_at": token_expires_at,
                    "sync_status": MicrosoftTeamsAccount.SyncStatus.ACTIVE,
                },
            )

            return Response(
                {
                    "message": "Microsoft Teams connected successfully",
                    "account": MicrosoftTeamsAccountSerializer(account).data,
                },
                status=status.HTTP_200_OK if created else status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Token exchange failed", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DisconnectMicrosoftTeamsView(APIView):
    """View to disconnect Microsoft Teams integration."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Disconnect the user's Microsoft Teams account."""
        try:
            account = MicrosoftTeamsAccount.objects.get(user=request.user)
        except MicrosoftTeamsAccount.DoesNotExist:
            return Response(
                {"error": "No Microsoft Teams account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Delete the account (this will cascade to related models)
        account.delete()

        return Response(
            {"message": "Microsoft Teams disconnected successfully"},
            status=status.HTTP_200_OK,
        )


class MicrosoftTeamsStatusView(APIView):
    """View to get Microsoft Teams integration status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the current status of the Microsoft Teams integration."""
        try:
            account = MicrosoftTeamsAccount.objects.get(user=request.user)
        except MicrosoftTeamsAccount.DoesNotExist:
            return Response(
                {
                    "is_connected": False,
                    "synced_teams_count": 0,
                    "synced_assignments_count": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Get last sync
        last_sync = SyncState.objects.filter(account=account).first()

        # Get counts
        synced_teams_count = SyncedTeam.objects.filter(account=account).count()
        synced_assignments_count = SyncedAssignment.objects.filter(
            synced_team__account=account
        ).count()

        data = {
            "is_connected": True,
            "account": MicrosoftTeamsAccountSerializer(account).data,
            "last_sync": SyncStateSerializer(last_sync).data if last_sync else None,
            "synced_teams_count": synced_teams_count,
            "synced_assignments_count": synced_assignments_count,
        }

        serializer = MicrosoftTeamsStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MicrosoftTeamsSyncView(APIView):
    """View to trigger Microsoft Teams sync."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Trigger a manual sync of Microsoft Teams data."""
        try:
            account = MicrosoftTeamsAccount.objects.get(user=request.user)
        except MicrosoftTeamsAccount.DoesNotExist:
            return Response(
                {"error": "No Microsoft Teams account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Start sync in background (for production, use Celery)
        # For now, run synchronously
        sync_service = MicrosoftTeamsSyncService(account)
        sync_state = sync_service.sync_all(sync_type=SyncState.SyncType.MANUAL)

        return Response(
            {
                "sync_started": True,
                "sync_state": SyncStateSerializer(sync_state).data,
            },
            status=status.HTTP_200_OK,
        )


class MicrosoftTeamsCoursesView(APIView):
    """View to list synced teams (courses)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_integrations_microsoft_teams_courses_list")
    def get(self, request):
        """Get all synced teams for the user."""
        try:
            account = MicrosoftTeamsAccount.objects.get(user=request.user)
        except MicrosoftTeamsAccount.DoesNotExist:
            return Response(
                {"error": "No Microsoft Teams account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        teams = SyncedTeam.objects.filter(account=account)
        from .serializers import SyncedTeamSerializer
        
        serializer = SyncedTeamSerializer(teams, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MicrosoftTeamsCourseDetailView(APIView):
    """View to get team details with channels and assignments."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_integrations_microsoft_teams_courses_retrieve")
    def get(self, request, team_id):
        """Get details of a specific synced team."""
        try:
            account = MicrosoftTeamsAccount.objects.get(user=request.user)
        except MicrosoftTeamsAccount.DoesNotExist:
            return Response(
                {"error": "No Microsoft Teams account connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            team = SyncedTeam.objects.get(
                id=team_id,
                account=account,
            )
        except SyncedTeam.DoesNotExist:
            return Response(
                {"error": "Team not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .serializers import SyncedTeamSerializer, SyncedChannelSerializer, SyncedAssignmentSerializer

        data = {
            "team": SyncedTeamSerializer(team).data,
            "channels": SyncedChannelSerializer(
                team.synced_channels.all(),
                many=True,
            ).data,
            "assignments": SyncedAssignmentSerializer(
                team.synced_assignments.all(),
                many=True,
            ).data,
        }

        return Response(data, status=status.HTTP_200_OK)
