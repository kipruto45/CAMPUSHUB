"""Admin configuration for recommendations."""

from django.contrib import admin

from .models import RecommendationCache, UserInterestProfile


@admin.register(UserInterestProfile)
class UserInterestProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "last_computed_at", "updated_at")
    search_fields = ("user__email", "user__full_name")
    readonly_fields = ("last_computed_at", "created_at", "updated_at")


@admin.register(RecommendationCache)
class RecommendationCacheAdmin(admin.ModelAdmin):
    list_display = ("user", "resource", "category", "score", "rank", "expires_at")
    list_filter = ("category",)
    search_fields = ("user__email", "resource__title")
    readonly_fields = ("created_at", "updated_at")
