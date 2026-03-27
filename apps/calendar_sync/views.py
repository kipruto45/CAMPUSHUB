"""
Views for Calendar Sync API
"""

from datetime import timedelta
import requests
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CalendarAccount, SyncedEvent, SyncSettings
from .services import CalendarSyncService, exchange_calendar_code, get_calendar_oauth_service
from .serializers import (
    CalendarAccountSerializer,
    SyncedEventSerializer,
    SyncSettingsSerializer,
)


class CalendarAccountListView(generics.ListCreateAPIView):
    """List connected calendars or connect a new one"""
    permission_classes = [IsAuthenticated]
    serializer_class = CalendarAccountSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return CalendarAccount.objects.none()
        return CalendarAccount.objects.filter(
            user=self.request.user,
            is_active=True
        )


class CalendarAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get or manage a specific calendar account"""
    permission_classes = [IsAuthenticated]
    serializer_class = CalendarAccountSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return CalendarAccount.objects.none()
        return CalendarAccount.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Soft delete - deactivate the account"""
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SyncCalendarView(generics.CreateAPIView):
    """Trigger a calendar sync"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        try:
            account = CalendarAccount.objects.get(pk=pk, user=request.user, is_active=True)
        except CalendarAccount.DoesNotExist:
            return Response(
                {'error': 'Calendar account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        days_ahead = int(request.data.get('days_ahead', 30))
        result = CalendarSyncService.sync_calendar(account, days_ahead)
        
        return Response(result)


class SyncedEventsListView(generics.ListAPIView):
    """List synced events from external calendars"""
    permission_classes = [IsAuthenticated]
    serializer_class = SyncedEventSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return SyncedEvent.objects.none()
        days = int(self.request.query_params.get('days', 30))
        return CalendarSyncService.get_user_calendar_events(
            self.request.user,
            days_ahead=days
        )


class SyncSettingsView(generics.RetrieveUpdateAPIView):
    """Get or update sync settings"""
    permission_classes = [IsAuthenticated]
    serializer_class = SyncSettingsSerializer

    def get_object(self):
        return CalendarSyncService.get_or_create_settings(self.request.user)


class ConnectGoogleView(generics.CreateAPIView):
    """Initiate Google Calendar OAuth flow"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from django.conf import settings

        google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        if not google_client_id:
            return Response(
                {'error': 'Google OAuth not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        redirect_uri = (
            str(request.data.get('redirect_uri') or '').strip()
            or str(getattr(settings, 'GOOGLE_REDIRECT_URI', '') or '').strip()
        )
        if not redirect_uri:
            return Response(
                {'error': 'Google redirect URI not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        state = str(request.data.get('state') or '').strip()
        auth_url = get_calendar_oauth_service('google').get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )

        return Response({
            'auth_url': auth_url,
            'provider': 'google',
            'redirect_uri': redirect_uri,
        })


class ConnectOutlookView(generics.CreateAPIView):
    """Initiate Outlook Calendar OAuth flow"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from django.conf import settings

        microsoft_client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
        if not microsoft_client_id:
            return Response(
                {'error': 'Microsoft OAuth not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        redirect_uri = (
            str(request.data.get('redirect_uri') or '').strip()
            or str(getattr(settings, 'MICROSOFT_REDIRECT_URI', '') or '').strip()
        )
        if not redirect_uri:
            return Response(
                {'error': 'Microsoft redirect URI not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        state = str(request.data.get('state') or '').strip()
        auth_url = get_calendar_oauth_service('outlook').get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )

        return Response({
            'auth_url': auth_url,
            'provider': 'outlook',
            'redirect_uri': redirect_uri,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_oauth_callback(request, *args, **kwargs):
    """Handle OAuth callback from Google or Outlook"""
    provider = str(request.data.get('provider') or '').strip().lower()
    code = str(request.data.get('code') or '').strip()
    redirect_uri = str(request.data.get('redirect_uri') or '').strip()
    
    if not provider or not code:
        return Response(
            {'error': 'Missing provider or code'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if provider not in {'google', 'outlook'}:
        return Response(
            {'error': 'Unsupported provider'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        exchange_result = exchange_calendar_code(
            provider=provider,
            code=code,
            redirect_uri=redirect_uri,
        )
    except ValueError as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except requests.RequestException as exc:
        return Response(
            {'error': f'Failed to exchange calendar authorization code: {exc}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    tokens = exchange_result['tokens']
    user_info = exchange_result['user_info']
    email = (
        str(
            user_info.get('email')
            or user_info.get('mail')
            or user_info.get('userPrincipalName')
            or request.data.get('email')
            or request.user.email
            or ''
        ).strip().lower()
    )
    calendar_id = str(request.data.get('calendar_id') or 'primary').strip() or 'primary'

    account = CalendarAccount.objects.filter(
        user=request.user,
        provider=provider,
        email=email,
    ).first()
    existing_refresh_token = account.refresh_token if account else ''

    account, created = CalendarAccount.objects.update_or_create(
        user=request.user,
        provider=provider,
        email=email,
        defaults={
            'access_token': str(tokens.get('access_token') or '').strip(),
            'refresh_token': str(tokens.get('refresh_token') or existing_refresh_token or '').strip(),
            'token_expires_at': timezone.now() + timedelta(
                seconds=int(tokens.get('expires_in', 3600) or 3600)
            ),
            'calendar_id': calendar_id,
            'is_active': True,
            'sync_enabled': True,
        }
    )

    return Response(
        CalendarAccountSerializer(account).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_event_to_calendar(request, *args, **kwargs):
    """Push a CampusHub event to connected calendars"""
    calendar_id = request.data.get('calendar_id')
    event_id = request.data.get('event_id')
    
    if not calendar_id or not event_id:
        return Response(
            {'error': 'Missing calendar_id or event_id'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        account = CalendarAccount.objects.get(
            pk=calendar_id,
            user=request.user,
            is_active=True
        )
    except CalendarAccount.DoesNotExist:
        return Response(
            {'error': 'Calendar account not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get the CampusHub event
    from apps.calendar.models import Event
    try:
        campus_event = Event.objects.get(pk=event_id, user=request.user)
    except Event.DoesNotExist:
        return Response(
            {'error': 'Event not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    result = CalendarSyncService.push_campus_event_to_calendar(account, campus_event)
    
    if result.get('success'):
        return Response(result)
    return Response(result, status=status.HTTP_400_BAD_REQUEST)
