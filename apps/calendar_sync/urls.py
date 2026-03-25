"""
URL routing for Calendar Sync
"""

from django.urls import path
from . import views

app_name = 'calendar_sync'

urlpatterns = [
    # Calendar accounts
    path('accounts/', views.CalendarAccountListView.as_view(), name='account-list'),
    path('accounts/<uuid:pk>/', views.CalendarAccountDetailView.as_view(), name='account-detail'),
    path('accounts/<uuid:pk>/sync/', views.SyncCalendarView.as_view(), name='sync-calendar'),
    
    # Events
    path('events/', views.SyncedEventsListView.as_view(), name='events-list'),
    
    # Settings
    path('settings/', views.SyncSettingsView.as_view(), name='settings'),
    
    # OAuth
    path('connect/google/', views.ConnectGoogleView.as_view(), name='connect-google'),
    path('connect/outlook/', views.ConnectOutlookView.as_view(), name='connect-outlook'),
    path('oauth/callback/', views.handle_oauth_callback, name='oauth-callback'),
    
    # Push events
    path('push-event/', views.push_event_to_calendar, name='push-event'),
]
