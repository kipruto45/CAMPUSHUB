"""
Admin configuration for Calendar Sync
"""

from django.contrib import admin
from .models import CalendarAccount, SyncedEvent, SyncSettings


@admin.register(CalendarAccount)
class CalendarAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'provider', 'email', 'sync_enabled', 'last_sync_at', 'is_active']
    list_filter = ['provider', 'is_active', 'sync_enabled']
    search_fields = ['user__email', 'email']
    raw_id_fields = ['user']


@admin.register(SyncedEvent)
class SyncedEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'calendar_account', 'start_time', 'end_time', 'is_deleted']
    list_filter = ['is_deleted', 'calendar_account__provider']
    search_fields = ['title', 'external_event_id']
    raw_id_fields = ['calendar_account']


@admin.register(SyncSettings)
class SyncSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'auto_sync', 'sync_direction', 'sync_interval_minutes']
    search_fields = ['user__email']
    raw_id_fields = ['user']
