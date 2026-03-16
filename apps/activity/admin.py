"""
Admin configuration for activity app.
"""

from django.contrib import admin

from .models import RecentActivity


@admin.register(RecentActivity)
class RecentActivityAdmin(admin.ModelAdmin):
    list_display = ["user", "activity_type", "target_title", "created_at"]
    list_filter = ["activity_type", "created_at"]
    search_fields = ["user__email", "metadata"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "user",
        "activity_type",
        "resource",
        "personal_file",
        "bookmark",
        "metadata",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False
