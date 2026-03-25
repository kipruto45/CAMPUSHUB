"""
Services for Calendar Sync
Google Calendar and Outlook Calendar integration
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional
from django.utils import timezone
from django.conf import settings

from .models import CalendarAccount, SyncedEvent, SyncSettings


class BaseCalendarService:
    """Base class for calendar services"""
    
    def __init__(self, account: CalendarAccount):
        self.account = account
        self.provider = account.provider
    
    def refresh_token_if_needed(self) -> bool:
        """Refresh the OAuth token if expired"""
        if not self.account.is_token_expired():
            return True
        
        # To be implemented with actual OAuth refresh logic
        # This would call the provider's token refresh endpoint
        return False
    
    def get_events(self, start_date, end_date) -> List[dict]:
        """Fetch events from the external calendar"""
        raise NotImplementedError
    
    def create_event(self, event_data: dict) -> dict:
        """Create an event in the external calendar"""
        raise NotImplementedError
    
    def update_event(self, event_id: str, event_data: dict) -> dict:
        """Update an event in the external calendar"""
        raise NotImplementedError
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the external calendar"""
        raise NotImplementedError


class GoogleCalendarService(BaseCalendarService):
    """Google Calendar API service"""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
    
    def __init__(self, account: CalendarAccount):
        super().__init__(account)
        self.base_url = 'https://www.googleapis.com/calendar/v3'
    
    def get_events(self, start_date, end_date) -> List[dict]:
        """Fetch events from Google Calendar"""
        if not self.refresh_token_if_needed():
            return []
        
        # Format dates for Google API
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        calendar_id = self.account.calendar_id or 'primary'
        
        # In production, this would use the Google API client
        # For now, return empty list as placeholder
        # The actual implementation would use google-api-python-client
        
        return []
    
    def create_event(self, event_data: dict) -> dict:
        """Create an event in Google Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        # Implementation would use Google Calendar API
        # events().insert(calendarId=calendar_id, body=event_data).execute()
        
        return {'id': 'new_event_id', 'status': 'confirmed'}
    
    def update_event(self, event_id: str, event_data: dict) -> dict:
        """Update an event in Google Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        return {'id': event_id, 'status': 'confirmed'}
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from Google Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        return True


class OutlookCalendarService(BaseCalendarService):
    """Microsoft Graph API service for Outlook Calendar"""
    
    GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'
    
    def __init__(self, account: CalendarAccount):
        super().__init__(account)
    
    def get_events(self, start_date, end_date) -> List[dict]:
        """Fetch events from Outlook Calendar"""
        if not self.refresh_token_if_needed():
            return []
        
        # Format dates for Microsoft Graph API
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        
        # In production, this would use Microsoft Graph API
        # GET /me/calendarView?startDateTime={start}&endDateTime={end}
        
        return []
    
    def create_event(self, event_data: dict) -> dict:
        """Create an event in Outlook Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        return {'id': 'new_event_id', 'status': 'confirmed'}
    
    def update_event(self, event_id: str, event_data: dict) -> dict:
        """Update an event in Outlook Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        return {'id': event_id, 'status': 'confirmed'}
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from Outlook Calendar"""
        if not self.refresh_token_if_needed():
            raise Exception("Token refresh failed")
        
        return True


class CalendarSyncService:
    """Main service for syncing calendars"""
    
    @staticmethod
    def get_service(account: CalendarAccount) -> BaseCalendarService:
        """Get the appropriate calendar service for the account"""
        if account.provider == 'google':
            return GoogleCalendarService(account)
        elif account.provider == 'outlook':
            return OutlookCalendarService(account)
        else:
            raise ValueError(f"Unsupported provider: {account.provider}")
    
    @staticmethod
    def sync_calendar(account: CalendarAccount, days_ahead: int = 30) -> dict:
        """Sync events from external calendar to CampusHub"""
        service = CalendarSyncService.get_service(account)
        
        if not account.sync_enabled:
            return {'synced': 0, 'errors': 0}
        
        start_date = timezone.now()
        end_date = start_date + timedelta(days=days_ahead)
        
        try:
            events = service.get_events(start_date, end_date)
            synced_count = 0
            error_count = 0
            
            for event_data in events:
                try:
                    SyncedEvent.objects.update_or_create(
                        calendar_account=account,
                        external_event_id=event_data.get('id', ''),
                        defaults={
                            'title': event_data.get('summary', ''),
                            'description': event_data.get('description', ''),
                            'start_time': event_data.get('start', {}).get('dateTime'),
                            'end_time': event_data.get('end', {}).get('dateTime'),
                            'location': event_data.get('location', {}).get('address', ''),
                            'is_all_day': event_data.get('start', {}).get('dateTime') is None,
                            'attendees': event_data.get('attendees', []),
                        }
                    )
                    synced_count += 1
                except Exception as e:
                    error_count += 1
            
            # Update last sync time
            account.last_sync_at = timezone.now()
            account.save()
            
            return {
                'synced': synced_count,
                'errors': error_count,
                'total': len(events),
            }
        except Exception as e:
            return {'synced': 0, 'errors': 1, 'error': str(e)}
    
    @staticmethod
    def push_campus_event_to_calendar(account: CalendarAccount, campus_event) -> dict:
        """Push a CampusHub event to the external calendar"""
        service = CalendarSyncService.get_service(account)
        
        # Convert CampusHub event to external calendar format
        if account.provider == 'google':
            event_data = {
                'summary': campus_event.title,
                'description': campus_event.description,
                'start': {
                    'dateTime': campus_event.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': campus_event.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'location': campus_event.location or '',
            }
        else:  # outlook
            event_data = {
                'subject': campus_event.title,
                'body': {
                    'contentType': 'text',
                    'content': campus_event.description,
                },
                'start': {
                    'dateTime': campus_event.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': campus_event.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'location': campus_event.location or '',
            }
        
        try:
            result = service.create_event(event_data)
            return {'success': True, 'external_id': result.get('id')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_or_create_settings(user) -> SyncSettings:
        """Get or create sync settings for a user"""
        settings, created = SyncSettings.objects.get_or_create(user=user)
        return settings
    
    @staticmethod
    def get_user_calendar_events(user, days_ahead: int = 30) -> List[SyncedEvent]:
        """Get all synced events for a user"""
        accounts = CalendarAccount.objects.filter(
            user=user,
            is_active=True,
            sync_enabled=True
        )
        
        start_date = timezone.now()
        end_date = start_date + timedelta(days=days_ahead)
        
        return SyncedEvent.objects.filter(
            calendar_account__in=accounts,
            start_time__gte=start_date,
            start_time__lte=end_date,
            is_deleted=False
        ).order_by('start_time')
