"""
Notes Admin Configuration
"""

from django.contrib import admin
from .models import Note, NoteShare, NoteVersion, NotePresence, NoteLock


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'status', 'folder', 'is_collaborative', 'created_at', 'updated_at']
    list_filter = ['status', 'is_collaborative', 'folder']
    search_fields = ['title', 'content', 'owner__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'title', 'content', 'content_html', 'status', 'folder')
        }),
        ('Owner & Tags', {
            'fields': ('owner', 'tags')
        }),
        ('Collaboration', {
            'fields': ('is_collaborative', 'lock_timeout')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NoteShare)
class NoteShareAdmin(admin.ModelAdmin):
    list_display = ['note', 'user', 'permission', 'is_active', 'can_share', 'can_copy', 'created_at']
    list_filter = ['permission', 'is_active']
    search_fields = ['note__title', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ['note', 'version_number', 'change_summary', 'created_by', 'created_at']
    list_filter = ['note']
    search_fields = ['note__title', 'change_summary']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(NotePresence)
class NotePresenceAdmin(admin.ModelAdmin):
    list_display = ['note', 'user', 'activity', 'cursor_position', 'is_online', 'last_active']
    list_filter = ['activity', 'is_online']
    search_fields = ['note__title', 'user__username']
    readonly_fields = ['id', 'last_active']


@admin.register(NoteLock)
class NoteLockAdmin(admin.ModelAdmin):
    list_display = ['note', 'user', 'lock_type', 'expires_at', 'created_at']
    list_filter = ['lock_type']
    search_fields = ['note__title', 'user__username']
    readonly_fields = ['id', 'created_at']