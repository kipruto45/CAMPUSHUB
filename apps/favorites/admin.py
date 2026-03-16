"""
Admin configuration for favorites app.
"""

from django.contrib import admin

from .models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "favorite_type", "target_title", "created_at"]
    list_filter = ["favorite_type", "created_at"]
    search_fields = ["user__email"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "user",
        "favorite_type",
        "resource",
        "personal_file",
        "personal_folder",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False
