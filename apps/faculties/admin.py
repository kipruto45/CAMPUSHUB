"""
Admin configuration for faculties app.
"""

from django.contrib import admin

from .models import Department, Faculty


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    """Admin configuration for Faculty model."""

    list_display = ["name", "code", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "code"]
    prepopulated_fields = {"slug": ("code",)}
    ordering = ["name"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""

    list_display = ["name", "code", "faculty", "slug", "is_active", "created_at"]
    list_filter = ["is_active", "faculty", "created_at"]
    search_fields = ["name", "code", "faculty__name"]
    prepopulated_fields = {"slug": ("code",)}
    ordering = ["faculty", "name"]
