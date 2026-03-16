"""
Admin configuration for ratings app.
"""

from django.contrib import admin

from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "value", "created_at"]
    list_filter = ["value", "created_at"]
    search_fields = ["user__email", "resource__title"]
    date_hierarchy = "created_at"
