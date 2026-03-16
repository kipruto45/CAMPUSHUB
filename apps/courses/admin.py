"""
Admin configuration for courses app.
"""

from django.contrib import admin

from .models import Course, Unit


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin configuration for Course model."""

    list_display = [
        "name",
        "code",
        "department",
        "duration_years",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "department", "duration_years", "created_at"]
    search_fields = ["name", "code", "department__name"]
    prepopulated_fields = {"slug": ("code",)}
    ordering = ["department", "name"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    """Admin configuration for Unit model."""

    list_display = [
        "name",
        "code",
        "course",
        "semester",
        "year_of_study",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "course", "semester", "year_of_study", "created_at"]
    search_fields = ["name", "code", "course__name"]
    prepopulated_fields = {"slug": ("code",)}
    ordering = ["course", "year_of_study", "semester", "code"]
