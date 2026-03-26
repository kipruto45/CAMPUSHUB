"""
Admin configuration for accounts app.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from .models import User, UserActivity, UserDevice


class UserChangeForm(BaseUserChangeForm):
    """Custom UserChangeForm that handles the username field properly."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make username non-required since it's optional in the custom User model
        if self.fields.get('username'):
            self.fields['username'].required = False
            # Also set empty_value to handle empty strings properly
            self.fields['username'].empty_value = ''
            # Override to_python to handle None values properly
            original_to_python = self.fields['username'].to_python
            def to_python_wrapper(value):
                if value is None or value == '':
                    return None
                return original_to_python(value)
            self.fields['username'].to_python = to_python_wrapper
        # Also make date_joined non-required for consistency
        if self.fields.get('date_joined'):
            self.fields['date_joined'].required = False

    def clean_username(self):
        """Handle username cleaning - allow None/empty values."""
        username = self.cleaned_data.get('username')
        # Return None if username is empty/None instead of raising error
        if not username:
            return None
        return username


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""

    form = UserChangeForm

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
