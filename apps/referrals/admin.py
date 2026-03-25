"""
Admin configuration for referral system.
"""

from django.contrib import admin

from .models import Referral, ReferralCode, RewardHistory, RewardTier


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    """Admin for referral codes."""

    list_display = [
        "code",
        "user",
        "is_active",
        "usage_count",
        "max_uses",
        "expires_at",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["code", "user__email", "user__first_name", "user__last_name"]
    readonly_fields = ["id", "code", "created_at", "updated_at", "usage_count"]
    ordering = ["-created_at"]

    def usage_count(self, obj):
        return obj.usage_count


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    """Admin for referrals."""

    list_display = [
        "id",
        "referrer",
        "email",
        "referee",
        "status",
        "rewards_claimed",
        "subscribed_at",
        "created_at",
    ]
    list_filter = ["status", "rewards_claimed", "created_at"]
    search_fields = [
        "referrer__email",
        "referee__email",
        "email",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"


@admin.register(RewardTier)
class RewardTierAdmin(admin.ModelAdmin):
    """Admin for reward tiers."""

    list_display = [
        "name",
        "min_referrals",
        "points",
        "premium_days",
        "badge",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "badge"]
    ordering = ["min_referrals"]


@admin.register(RewardHistory)
class RewardHistoryAdmin(admin.ModelAdmin):
    """Admin for reward history."""

    list_display = [
        "user",
        "reward_type",
        "reward_value",
        "referral",
        "created_at",
    ]
    list_filter = ["reward_type", "created_at"]
    search_fields = ["user__email", "description"]
    readonly_fields = ["id", "created_at"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
