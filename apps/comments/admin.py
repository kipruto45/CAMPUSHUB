"""
Admin configuration for comments app.
"""

from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "resource",
        "content_preview",
        "is_edited",
        "is_deleted",
        "created_at",
    ]
    list_filter = ["is_edited", "is_deleted", "created_at"]
    search_fields = ["user__email", "resource__title", "content"]
    date_hierarchy = "created_at"

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Content"
