"""
Gamification serializers for API responses.
"""

from rest_framework import serializers

from .models import (
    PointCategory,
    PointAction,
    UserPoints,
    PointTransaction,
    BadgeCategory,
    BadgeLevel,
    Badge,
    UserBadge,
    Leaderboard,
    UserStreak,
    StreakHistory,
    StreakReward,
    Achievement,
    AchievementTier,
    AchievementCategory,
    UserAchievement,
)


class PointCategorySerializer(serializers.ModelSerializer):
    """Serializer for point categories."""

    class Meta:
        model = PointCategory
        fields = ["id", "name", "description", "icon"]


class PointActionSerializer(serializers.ModelSerializer):
    """Serializer for point actions."""

    category = PointCategorySerializer(read_only=True)

    class Meta:
        model = PointAction
        fields = ["id", "name", "category", "points", "description", "max_times_per_day"]


class UserPointsSerializer(serializers.ModelSerializer):
    """Serializer for user points."""

    class Meta:
        model = UserPoints
        fields = [
            "total_points",
            "level",
            "learning_points",
            "engagement_points",
            "contribution_points",
            "achievement_points",
            "points_to_next_level",
            "current_level_points",
            "points_for_next_level",
        ]


class PointTransactionSerializer(serializers.ModelSerializer):
    """Serializer for point transactions."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    action_name = serializers.CharField(source="action.name", read_only=True)

    class Meta:
        model = PointTransaction
        fields = [
            "id",
            "points",
            "category_name",
            "action_name",
            "balance_after",
            "description",
            "reference_id",
            "reference_type",
            "created_at",
        ]


class BadgeCategorySerializer(serializers.ModelSerializer):
    """Serializer for badge categories."""

    class Meta:
        model = BadgeCategory
        fields = ["id", "name", "description", "icon"]


class BadgeLevelSerializer(serializers.ModelSerializer):
    """Serializer for badge levels."""

    class Meta:
        model = BadgeLevel
        fields = ["id", "name", "multiplier", "icon", "color"]


class BadgeSerializer(serializers.ModelSerializer):
    """Serializer for badges."""

    category = BadgeCategorySerializer(read_only=True)
    level = BadgeLevelSerializer(read_only=True)

    class Meta:
        model = Badge
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "level",
            "description",
            "icon",
            "points_required",
            "action_count_required",
        ]


class UserBadgeSerializer(serializers.ModelSerializer):
    """Serializer for user badges."""

    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "earned_at"]


class BadgeProgressSerializer(serializers.Serializer):
    """Serializer for badge progress."""

    badge = BadgeSerializer(read_only=True)
    progress_percent = serializers.FloatField()
    points_required = serializers.IntegerField()
    current_points = serializers.IntegerField()


class LeaderboardEntrySerializer(serializers.Serializer):
    """Serializer for leaderboard entries."""

    rank = serializers.IntegerField()
    user_id = serializers.CharField()
    user_name = serializers.CharField()
    user_email = serializers.EmailField()
    profile_image = serializers.CharField(allow_null=True)
    faculty = serializers.CharField(allow_null=True)
    department = serializers.CharField(allow_null=True)
    points = serializers.IntegerField()
    level = serializers.IntegerField(required=False)


class AwardPointsRequestSerializer(serializers.Serializer):
    """Serializer for awarding points requests."""

    user_id = serializers.CharField(required=False)
    action_name = serializers.CharField(required=False)
    category_name = serializers.CharField(required=False)
    points = serializers.IntegerField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.CharField(required=False, allow_blank=True)
    reference_type = serializers.CharField(required=False, allow_blank=True)


class StreakHistorySerializer(serializers.ModelSerializer):
    """Serializer for streak history."""

    class Meta:
        model = StreakHistory
        fields = [
            "id",
            "date",
            "activity_count",
            "points_earned",
            "streak_at_date",
            "milestone_reached",
            "created_at",
        ]


class UserStreakSerializer(serializers.ModelSerializer):
    """Serializer for user streak."""

    class Meta:
        model = UserStreak
        fields = [
            "id",
            "user",
            "current_streak",
            "longest_streak",
            "last_activity_date",
            "is_frozen",
            "freeze_start_date",
            "streak_freezes",
            "created_at",
            "updated_at",
        ]


class StreakStatusSerializer(serializers.Serializer):
    """Serializer for streak status response."""

    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    last_activity_date = serializers.DateField(allow_null=True)
    is_frozen = serializers.BooleanField()
    streak_freezes_remaining = serializers.IntegerField()
    next_milestone = serializers.IntegerField(allow_null=True)
    days_until_next_milestone = serializers.IntegerField()
    activity_threshold = serializers.IntegerField()


# ============== Achievement Serializers ==============


class AchievementTierSerializer(serializers.ModelSerializer):
    """Serializer for achievement tiers."""

    class Meta:
        model = AchievementTier
        fields = ["id", "name", "multiplier", "icon", "color"]


class AchievementCategorySerializer(serializers.ModelSerializer):
    """Serializer for achievement categories."""

    class Meta:
        model = AchievementCategory
        fields = ["id", "name", "description", "icon"]


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for achievements."""

    category = AchievementCategorySerializer(read_only=True)
    tier = AchievementTierSerializer(read_only=True)
    badge_name = serializers.CharField(source="badge.name", read_only=True, allow_null=True)

    class Meta:
        model = Achievement
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "tier",
            "description",
            "icon",
            "target_value",
            "target_type",
            "points_reward",
            "premium_days_reward",
            "badge",
            "badge_name",
            "profile_customization",
            "is_featured",
            "order",
        ]


class UserAchievementSerializer(serializers.ModelSerializer):
    """Serializer for user achievements."""

    achievement = AchievementSerializer(read_only=True)
    progress_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = UserAchievement
        fields = [
            "id",
            "achievement",
            "current_progress",
            "is_completed",
            "completed_at",
            "is_reward_claimed",
            "claimed_at",
            "progress_percent",
            "created_at",
            "updated_at",
        ]


class AchievementProgressSerializer(serializers.Serializer):
    """Serializer for achievement progress response."""

    achievement = serializers.DictField()
    user_progress = serializers.DictField()


class AchievementStatsSerializer(serializers.Serializer):
    """Serializer for achievement statistics."""

    total_achievements = serializers.IntegerField()
    completed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    rewards_claimed = serializers.IntegerField()
    completion_percent = serializers.FloatField()
    points_earned = serializers.IntegerField()


class ClaimRewardResponseSerializer(serializers.Serializer):
    """Serializer for claim reward response."""

    success = serializers.BooleanField()
    message = serializers.CharField()
    rewards = serializers.DictField()
