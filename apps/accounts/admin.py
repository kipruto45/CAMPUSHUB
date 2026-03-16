"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserActivity, UserDevice


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""

    list_display = [
        "email",
        "get_full_name",
        "course",
        "year_of_study",
        "is_verified",
        "is_active",
        "date_joined",
    ]
    list_filter = ["is_verified", "is_active", "date_joined", "course"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering = ["-date_joined"]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Academic Info", {"fields": ("course", "year_of_study", "student_id")}),
        (
            "Profile Info",
            {"fields": ("profile_image", "bio", "phone", "date_of_birth")},
        ),
        ("Status", {"fields": ("is_verified", "is_suspended", "suspension_reason")}),
        ("Activity", {"fields": ("login_count", "last_activity")}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Academic Info", {"fields": ("course", "year_of_study")}),
    )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """Admin configuration for UserActivity model."""

    list_display = ["user", "action", "ip_address", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["user__email", "description"]
    date_hierarchy = "created_at"


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    """Admin configuration for UserDevice model."""

    list_display = ["user", "device_type", "device_name", "is_active", "last_used"]
    list_filter = ["device_type", "is_active"]
    search_fields = ["user__email", "device_name", "token"]
    date_hierarchy = "created_at"
