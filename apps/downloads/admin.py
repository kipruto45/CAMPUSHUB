"""
Admin configuration for downloads app.
"""

from django.contrib import admin

from .models import Download


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "ip_address", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "resource__title"]
    date_hierarchy = "created_at"
