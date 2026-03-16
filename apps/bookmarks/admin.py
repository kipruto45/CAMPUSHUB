"""
Admin configuration for bookmarks app.
"""

from django.contrib import admin

from .models import Bookmark


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "resource__title"]
    date_hierarchy = "created_at"
