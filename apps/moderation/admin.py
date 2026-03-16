"""
Admin configuration for moderation app.
"""

from django.contrib import admin

from .models import ModerationLog


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ["target", "reviewed_by", "action", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["resource__title", "comment__content", "reviewed_by__email"]
    date_hierarchy = "created_at"

    def target(self, obj):
        if obj.comment_id:
            return f"Comment #{obj.comment_id}"
        if obj.resource_id:
            return obj.resource.title
        return "-"
