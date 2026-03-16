"""
Admin configuration for notifications app.
"""

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "title", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read", "created_at"]
    search_fields = ["recipient__email", "title", "message"]
    date_hierarchy = "created_at"
