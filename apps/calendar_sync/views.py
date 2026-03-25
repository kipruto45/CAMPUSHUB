"""
Views for Calendar Sync API
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CalendarAccount, SyncedEvent, SyncSettings
from .services import CalendarSyncService
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
        return CalendarAccount.objects.filter(
            user=self.request.user,
            is_active=True
        )


class CalendarAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get or manage a specific calendar account"""
    permission_classes = [IsAuthenticated]
    serializer_class = CalendarAccountSerializer

    def get_queryset(self):
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

    def post(self, request, pk):
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

    def post(self, request):
        # In a real implementation, this would:
        # 1. Generate OAuth URL with Google
        # 2. Return the URL to the frontend
        # 3. Handle the callback
        
        from django.conf import settings
        
        redirect_uri = request.data.get('redirect_uri', '')
        
        # Google OAuth configuration
        google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        
        if not google_client_id:
            return Response(
                {'error': 'Google OAuth not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Build OAuth URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={google_client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=https://www.googleapis.com/auth/calendar.events.readonly&"
            f"access_type=offline"
        )
        
        return Response({
            'auth_url': auth_url,
            'provider': 'google',
        })


class ConnectOutlookView(generics.CreateAPIView):
    """Initiate Outlook Calendar OAuth flow"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.conf import settings
        
        redirect_uri = request.data.get('redirect_uri', '')
        
        # Microsoft OAuth configuration
        microsoft_client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
        
        if not microsoft_client_id:
            return Response(
                {'error': 'Microsoft OAuth not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Build OAuth URL
        auth_url = (
            f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
            f"client_id={microsoft_client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=Calendars.ReadWrite offline_access"
        )
        
        return Response({
            'auth_url': auth_url,
            'provider': 'outlook',
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_oauth_callback(request):
    """Handle OAuth callback from Google or Outlook"""
    provider = request.data.get('provider')
    code = request.data.get('code')
    
    if not provider or not code:
        return Response(
            {'error': 'Missing provider or code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # In production, exchange code for tokens
    # This is a placeholder implementation
    
    # Create or update calendar account
    account, created = CalendarAccount.objects.update_or_create(
        user=request.user,
        provider=provider,
        email=request.data.get('email', ''),
        defaults={
            'access_token': 'placeholder_token',
            'refresh_token': 'placeholder_refresh',
            'token_expires_at': timezone.now() + timedelta(hours=1),
            'calendar_id': request.data.get('calendar_id', 'primary'),
            'is_active': True,
        }
    )
    
    return Response(
        CalendarAccountSerializer(account).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_event_to_calendar(request):
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
