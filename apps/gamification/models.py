"""
Gamification models for CampusHub.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class PointCategory(models.Model):
    """Categories for points (Learning, Engagement, Contribution, Achievement)."""

    CATEGORY_CHOICES = [
        ("learning", "Learning"),
        ("engagement", "Engagement"),
        ("contribution", "Contribution"),
        ("achievement", "Achievement"),
    ]

    name = models.CharField(max_length=50, unique=True, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or identifier")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_point_categories"
        verbose_name = "Point Category"
        verbose_name_plural = "Point Categories"

    def __str__(self):
        return self.get_name_display()


class PointAction(models.Model):
    """Defines actions that can earn points."""

    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        PointCategory,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    points = models.IntegerField(default=0, help_text="Points awarded for this action")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    max_times_per_day = models.PositiveIntegerField(
        default=1,
        help_text="Maximum times this action can be performed per day",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_point_actions"
        verbose_name = "Point Action"
        verbose_name_plural = "Point Actions"

    def __str__(self):
        return f"{self.name} ({self.points} points)"


class UserPoints(models.Model):
    """Tracks point history and a summary row per user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ACTION_CHOICES = [
        ("__summary__", "Summary"),
        ("upload_resource", "Upload Resource"),
        ("download_resource", "Download Resource"),
        ("rate_resource", "Rate Resource"),
        ("comment_resource", "Comment Resource"),
        ("daily_login", "Daily Login"),
        ("share_resource", "Share Resource"),
        ("verify_email", "Verify Email"),
        ("earn_badge", "Earn Badge"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gamification_points",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default="__summary__")
    points = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    total_points = models.PositiveIntegerField(default=0)
    learning_points = models.PositiveIntegerField(default=0)
    engagement_points = models.PositiveIntegerField(default=0)
    contribution_points = models.PositiveIntegerField(default=0)
    achievement_points = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_user_points"
        verbose_name = "User Points"
        verbose_name_plural = "User Points"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "action", "-created_at"])]

    def __str__(self):
        if self.action == "__summary__":
            return f"{self.user.email} - {self.total_points} points (Level {self.level})"
        return f"{self.user.email} - {self.action} ({self.points} points)"


class UserStats(models.Model):
    """Legacy-compatible gamification counters."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gamification_stats",
    )
    total_points = models.IntegerField(default=0)
    total_uploads = models.IntegerField(default=0)
    total_downloads = models.IntegerField(default=0)
    total_ratings = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    total_shares = models.IntegerField(default=0)
    consecutive_login_days = models.IntegerField(default=0)
    last_login_date = models.DateField(null=True, blank=True)
    resources_shared = models.IntegerField(default=0)
    resources_saved = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_user_stats"
        verbose_name = "User Stats"
        verbose_name_plural = "User Stats"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.total_points} points"


class PointTransaction(models.Model):
    """Tracks individual point transactions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_transactions",
    )
    action = models.ForeignKey(
        PointAction,
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        PointCategory,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    points = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference ID for related object (e.g., task ID, study session ID)",
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of reference (e.g., 'task', 'study_session', 'referral')",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gamification_point_transactions"
        verbose_name = "Point Transaction"
        verbose_name_plural = "Point Transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reference_id", "reference_type"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.points} points ({self.category.name})"


class BadgeCategory(models.Model):
    """Categories for badges (Learning, Social, Streak, Special)."""

    CATEGORY_CHOICES = [
        ("uploads", "Uploads"),
        ("downloads", "Downloads"),
        ("engagement", "Engagement"),
        ("learning", "Learning"),
        ("social", "Social"),
        ("streak", "Streak"),
        ("special", "Special"),
    ]

    name = models.CharField(max_length=50, unique=True, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_badge_categories"
        verbose_name = "Badge Category"
        verbose_name_plural = "Badge Categories"

    def __str__(self):
        return self.get_name_display()


class BadgeLevel(models.Model):
    """Levels for badges (Bronze, Silver, Gold, Platinum)."""

    LEVEL_CHOICES = [
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
    ]

    name = models.CharField(max_length=20, unique=True, choices=LEVEL_CHOICES)
    multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        help_text="Point multiplier for this badge level",
    )
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True, help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gamification_badge_levels"
        verbose_name = "Badge Level"
        verbose_name_plural = "Badge Levels"
        ordering = ["id"]

    def __str__(self):
        return self.get_name_display()


class BadgeManager(models.Manager):
    """Manager that accepts legacy string category values."""

    def create(self, **kwargs):
        category = kwargs.get("category")
        if isinstance(category, str):
            category_obj, _ = BadgeCategory.objects.get_or_create(
                name=category,
                defaults={"description": "", "icon": ""},
            )
            kwargs["category"] = category_obj
        return super().create(**kwargs)


class Badge(models.Model):
    """Achievement badges for milestones."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.ForeignKey(
        BadgeCategory,
        on_delete=models.CASCADE,
        related_name="badges",
        null=True,
        blank=True,
    )
    level = models.ForeignKey(
        BadgeLevel,
        on_delete=models.CASCADE,
        related_name="badges",
        null=True,
        blank=True,
    )
    description = models.TextField(default="")
    icon = models.CharField(max_length=50, blank=True)
    points_required = models.PositiveIntegerField(
        default=0,
        help_text="Total points required to earn this badge",
    )
    requirement_type = models.CharField(max_length=50, blank=True, default="")
    requirement_value = models.IntegerField(default=0)
    action_count_required = models.PositiveIntegerField(
        default=0,
        help_text="Number of times the action must be performed",
    )
    related_action = models.ForeignKey(
        PointAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badges",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BadgeManager()

    class Meta:
        db_table = "gamification_badges"
        verbose_name = "Badge"
        verbose_name_plural = "Badges"
        ordering = ["level", "category", "name"]

    def save(self, *args, **kwargs):
        if isinstance(self.category, str):
            category_obj, _ = BadgeCategory.objects.get_or_create(
                name=self.category,
                defaults={"description": "", "icon": ""},
            )
            self.category = category_obj
        super().save(*args, **kwargs)

    def __str__(self):
        category_name = getattr(getattr(self, "category", None), "name", "") or ""
        level_name = getattr(getattr(self, "level", None), "name", "") or ""
        detail = " ".join([x for x in [level_name, category_name] if x]).strip()
        return f"{self.name} ({detail})" if detail else self.name


class UserBadge(models.Model):
    """Tracks badges earned by users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    earned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "gamification_user_badges"
        verbose_name = "User Badge"
        verbose_name_plural = "User Badges"
        ordering = ["-earned_at"]
        unique_together = ["user", "badge"]

    def __str__(self):
        return f"{self.user.email} - {self.badge.name}"


class Leaderboard(models.Model):
    """Stores leaderboard snapshots."""

    TYPE_CHOICES = [
        ("global", "Global"),
        ("faculty", "Faculty"),
        ("department", "Department"),
    ]

    PERIOD_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("all_time", "All Time"),
    ]

    leaderboard_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="global")
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default="weekly")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaderboard_rankings",
        null=True,
        blank=True,
    )
    rank = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    faculty_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Faculty ID for faculty leaderboards",
    )
    department_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Department ID for department leaderboards",
    )
    snapshot_data = models.JSONField(
        default=dict,
        help_text="JSON containing ranked user data",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_leaderboards"
        verbose_name = "Leaderboard"
        verbose_name_plural = "Leaderboards"
        ordering = ["period", "rank", "-created_at"]
        indexes = [
            models.Index(fields=["leaderboard_type", "period", "-created_at"]),
        ]
        unique_together = [("period", "user")]

    def __str__(self):
        if self.user_id:
            return f"{self.user.get_full_name() or self.user.email} - #{self.rank} ({self.period})"
        return f"{self.leaderboard_type} - {self.period} ({self.created_at.date()})"


class UserStreak(models.Model):
    """Tracks daily engagement streaks for users."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streak",
    )
    current_streak = models.PositiveIntegerField(default=0, help_text="Current consecutive days streak")
    longest_streak = models.PositiveIntegerField(default=0, help_text="Longest streak ever achieved")
    last_activity_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last recorded activity",
    )
    streak_freezes = models.PositiveIntegerField(
        default=1,
        help_text="Number of streak freezes available (max 1)",
    )
    is_frozen = models.BooleanField(
        default=False,
        help_text="Whether streak is currently frozen",
    )
    freeze_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when streak was frozen",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_user_streaks"
        verbose_name = "User Streak"
        verbose_name_plural = "User Streaks"

    def __str__(self):
        return f"{self.user.email} - {self.current_streak} day streak"


class StreakHistory(models.Model):
    """Stores historical records of streak activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streak_history",
    )
    date = models.DateField(help_text="Date of activity")
    activity_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of activities on this day",
    )
    points_earned = models.PositiveIntegerField(
        default=0,
        help_text="Points earned on this day",
    )
    streak_at_date = models.PositiveIntegerField(
        default=0,
        help_text="Streak length on this date",
    )
    milestone_reached = models.CharField(
        max_length=20,
        blank=True,
        help_text="Milestone reached (7, 30, 100)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gamification_streak_history"
        verbose_name = "Streak History"
        verbose_name_plural = "Streak Histories"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"]),
        ]
        unique_together = ["user", "date"]

    def __str__(self):
        return f"{self.user.email} - {self.date} ({self.activity_count} activities)"


class StreakReward(models.Model):
    """Defines rewards for streak milestones."""

    STREAK_CHOICES = [
        (7, "7 Days"),
        (30, "30 Days"),
        (100, "100 Days"),
    ]

    REWARD_TYPE_CHOICES = [
        ("points", "Points"),
        ("badge", "Badge"),
        ("both", "Both"),
    ]

    streak_milestone = models.PositiveIntegerField(choices=STREAK_CHOICES)
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPE_CHOICES)
    bonus_points = models.PositiveIntegerField(default=0, help_text="Bonus points awarded")
    badge = models.ForeignKey(
        Badge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="streak_rewards",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gamification_streak_rewards"
        verbose_name = "Streak Reward"
        verbose_name_plural = "Streak Rewards"
        unique_together = ["streak_milestone"]

    def __str__(self):
        return f"{self.streak_milestone} day streak - {self.reward_type}"


# Achievement Tiers
ACHIEVEMENT_TIER_CHOICES = [
    ("bronze", "Bronze"),
    ("silver", "Silver"),
    ("gold", "Gold"),
    ("diamond", "Diamond"),
]

# Achievement Categories
ACHIEVEMENT_CATEGORY_CHOICES = [
    ("learning", "Learning"),
    ("social", "Social"),
    ("engagement", "Engagement"),
    ("special", "Special"),
]

# Reward Types
REWARD_TYPE_CHOICES = [
    ("points", "Points"),
    ("badge", "Badge"),
    ("profile_customization", "Profile Customization"),
    ("premium_days", "Premium Days"),
]


class AchievementTier(models.Model):
    """Tiers for achievements (Bronze, Silver, Gold, Diamond)."""

    name = models.CharField(max_length=20, unique=True, choices=ACHIEVEMENT_TIER_CHOICES)
    multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        help_text="Point multiplier for this tier",
    )
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True, help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gamification_achievement_tiers"
        verbose_name = "Achievement Tier"
        verbose_name_plural = "Achievement Tiers"
        ordering = ["id"]

    def __str__(self):
        return self.get_name_display()


class AchievementCategory(models.Model):
    """Categories for achievements (Learning, Social, Engagement, Special)."""

    name = models.CharField(max_length=50, unique=True, choices=ACHIEVEMENT_CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_achievement_categories"
        verbose_name = "Achievement Category"
        verbose_name_plural = "Achievement Categories"

    def __str__(self):
        return self.get_name_display()


class Achievement(models.Model):
    """Achievement milestones that users can achieve."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="Untitled Achievement")
    slug = models.SlugField(max_length=100, unique=True, default="")
    title = models.CharField(max_length=200, blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievement_events",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        AchievementCategory,
        on_delete=models.CASCADE,
        related_name="achievements",
        null=True,
        blank=True,
    )
    tier = models.ForeignKey(
        AchievementTier,
        on_delete=models.CASCADE,
        related_name="achievements",
        null=True,
        blank=True,
    )
    description = models.TextField(default="")
    icon = models.CharField(max_length=50, blank=True)
    
    # Target requirements
    target_value = models.PositiveIntegerField(
        default=1,
        help_text="Target value to complete the achievement",
    )
    target_type = models.CharField(
        max_length=50,
        default="default",
        help_text="Type of target: courses_completed, study_hours, posts_count, streak_days, etc.",
    )
    
    # Rewards
    points_reward = models.PositiveIntegerField(default=0, help_text="Points awarded on completion")
    points_earned = models.IntegerField(default=0)
    milestone_type = models.CharField(max_length=50, blank=True, default="")
    premium_days_reward = models.PositiveIntegerField(
        default=0, 
        help_text="Premium days awarded on completion",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="achievements",
        help_text="Badge awarded on completion",
    )
    profile_customization = models.CharField(
        max_length=100,
        blank=True,
        help_text="Profile customization unlocked on completion",
    )
    
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Featured on achievement page")
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_achievements"
        verbose_name = "Achievement"
        verbose_name_plural = "Achievements"
        ordering = ["tier", "category", "order", "name"]
        unique_together = ["slug"]

    def __str__(self):
        title = self.title or self.name
        if self.user_id:
            return f"{title} - {self.user.get_full_name() or self.user.email}"
        category_name = getattr(getattr(self, "category", None), "name", "") or ""
        tier_name = getattr(getattr(self, "tier", None), "name", "") or ""
        detail = " ".join([x for x in [tier_name, category_name] if x]).strip()
        return f"{title} ({detail})" if detail else title


class UserAchievement(models.Model):
    """Tracks user progress and completion of achievements."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements",
    )
    current_progress = models.PositiveIntegerField(default=0, help_text="Current progress value")
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when achievement was completed",
    )
    is_reward_claimed = models.BooleanField(default=False, help_text="Whether reward has been claimed")
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when reward was claimed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_user_achievements"
        verbose_name = "User Achievement"
        verbose_name_plural = "User Achievements"
        ordering = ["-completed_at", "-updated_at"]
        unique_together = ["user", "achievement"]

    def __str__(self):
        return f"{self.user.email} - {self.achievement.name}"

    @property
    def progress_percent(self):
        """Calculate progress percentage."""
        if self.achievement.target_value == 0:
            return 0
        return min(100, (self.current_progress / self.achievement.target_value) * 100)


# Default achievement tiers
DEFAULT_ACHIEVEMENT_TIERS = [
    {"name": "bronze", "multiplier": 1.0, "icon": "bronze", "color": "#cd7f32"},
    {"name": "silver", "multiplier": 1.5, "icon": "silver", "color": "#c0c0c0"},
    {"name": "gold", "multiplier": 2.0, "icon": "gold", "color": "#ffd700"},
    {"name": "diamond", "multiplier": 3.0, "icon": "diamond", "color": "#b9f2ff"},
]

# Default achievement categories
DEFAULT_ACHIEVEMENT_CATEGORIES = [
    {"name": "learning", "description": "Achievements for learning activities", "icon": "book"},
    {"name": "social", "description": "Achievements for social interactions", "icon": "users"},
    {"name": "engagement", "description": "Achievements for engagement and activity", "icon": "zap"},
    {"name": "special", "description": "Special event achievements", "icon": "star"},
]

# Default achievements
DEFAULT_ACHIEVEMENTS = [
    # Learning - Bronze
    {"name": "First Lesson", "slug": "first_lesson", "category": "learning", "tier": "bronze",
     "description": "Complete your first lesson", "icon": "book-open", "target_value": 1, "target_type": "lessons_completed",
     "points_reward": 25, "order": 1},
    {"name": "Course Starter", "slug": "course_starter", "category": "learning", "tier": "bronze",
     "description": "Complete your first course", "icon": "graduation-cap", "target_value": 1, "target_type": "courses_completed",
     "points_reward": 50, "order": 2},
    {"name": "Study Session Initiator", "slug": "study_session_initiator", "category": "learning", "tier": "bronze",
     "description": "Complete 10 study sessions", "icon": "clock", "target_value": 10, "target_type": "study_sessions",
     "points_reward": 30, "order": 3},
    
    # Learning - Silver
    {"name": "Dedicated Learner", "slug": "dedicated_learner", "category": "learning", "tier": "silver",
     "description": "Complete 5 courses", "icon": "award", "target_value": 5, "target_type": "courses_completed",
     "points_reward": 150, "premium_days_reward": 3, "order": 4},
    {"name": "Study Marathon", "slug": "study_marathon", "category": "learning", "tier": "silver",
     "description": "Complete 50 study sessions", "icon": "activity", "target_value": 50, "target_type": "study_sessions",
     "points_reward": 100, "order": 5},
    
    # Learning - Gold
    {"name": "Knowledge Seeker", "slug": "knowledge_seeker", "category": "learning", "tier": "gold",
     "description": "Complete 10 courses", "icon": "book", "target_value": 10, "target_type": "courses_completed",
     "points_reward": 300, "premium_days_reward": 7, "order": 6},
    {"name": "Study Champion", "slug": "study_champion", "category": "learning", "tier": "gold",
     "description": "Complete 100 study sessions", "icon": "trophy", "target_value": 100, "target_type": "study_sessions",
     "points_reward": 250, "order": 7},
    
    # Learning - Diamond
    {"name": "Master Scholar", "slug": "master_scholar", "category": "learning", "tier": "diamond",
     "description": "Complete 25 courses", "icon": "star", "target_value": 25, "target_type": "courses_completed",
     "points_reward": 500, "premium_days_reward": 14, "order": 8},
    
    # Social - Bronze
    {"name": "First Friend", "slug": "first_friend", "category": "social", "tier": "bronze",
     "description": "Help your first peer", "icon": "user-plus", "target_value": 1, "target_type": "peers_helped",
     "points_reward": 25, "order": 10},
    {"name": "Forum Participant", "slug": "forum_participant", "category": "social", "tier": "bronze",
     "description": "Make your first forum post", "icon": "message-circle", "target_value": 1, "target_type": "forum_posts",
     "points_reward": 20, "order": 11},
    
    # Social - Silver
    {"name": "Community Helper", "slug": "community_helper", "category": "social", "tier": "silver",
     "description": "Help 10 peers", "icon": "heart", "target_value": 10, "target_type": "peers_helped",
     "points_reward": 100, "order": 12},
    {"name": "Active Discusser", "slug": "active_discusser", "category": "social", "tier": "silver",
     "description": "Make 25 forum posts", "icon": "message-square", "target_value": 25, "target_type": "forum_posts",
     "points_reward": 75, "order": 13},
    
    # Social - Gold
    {"name": "Community Champion", "slug": "community_champion", "category": "social", "tier": "gold",
     "description": "Help 50 peers", "icon": "users", "target_value": 50, "target_type": "peers_helped",
     "points_reward": 250, "premium_days_reward": 5, "order": 14},
    
    # Social - Diamond
    {"name": "Legendary Mentor", "slug": "legendary_mentor", "category": "social", "tier": "diamond",
     "description": "Help 100 peers", "icon": "star", "target_value": 100, "target_type": "peers_helped",
     "points_reward": 500, "premium_days_reward": 14, "order": 15},
    
    # Engagement - Bronze
    {"name": "Daily Visitor", "slug": "daily_visitor", "category": "engagement", "tier": "bronze",
     "description": "Log in for 3 consecutive days", "icon": "calendar", "target_value": 3, "target_type": "streak_days",
     "points_reward": 30, "order": 20},
    {"name": "Active User", "slug": "active_user", "category": "engagement", "tier": "bronze",
     "description": "Log in for 7 consecutive days", "icon": "zap", "target_value": 7, "target_type": "streak_days",
     "points_reward": 50, "order": 21},
    
    # Engagement - Silver
    {"name": "Weekly Regular", "slug": "weekly_regular", "category": "engagement", "tier": "silver",
     "description": "Log in for 14 consecutive days", "icon": "calendar-check", "target_value": 14, "target_type": "streak_days",
     "points_reward": 100, "order": 22},
    {"name": "Engaged Member", "slug": "engaged_member", "category": "engagement", "tier": "silver",
     "description": "Log in for 30 consecutive days", "icon": "fire", "target_value": 30, "target_type": "streak_days",
     "points_reward": 200, "premium_days_reward": 3, "order": 23},
    
    # Engagement - Gold
    {"name": "Dedicated Daily", "slug": "dedicated_daily", "category": "engagement", "tier": "gold",
     "description": "Log in for 60 consecutive days", "icon": "sun", "target_value": 60, "target_type": "streak_days",
     "points_reward": 350, "premium_days_reward": 7, "order": 24},
    
    # Engagement - Diamond
    {"name": "Unstoppable", "slug": "unstoppable", "category": "engagement", "tier": "diamond",
     "description": "Log in for 100 consecutive days", "icon": "rocket", "target_value": 100, "target_type": "streak_days",
     "points_reward": 500, "premium_days_reward": 14, "order": 25},
    
    # Special - Bronze
    {"name": "First Referral", "slug": "first_referral", "category": "special", "tier": "bronze",
     "description": "Refer your first friend", "icon": "user-check", "target_value": 1, "target_type": "referrals",
     "points_reward": 50, "order": 30},
    
    # Special - Silver
    {"name": "Network Builder", "slug": "network_builder", "category": "special", "tier": "silver",
     "description": "Refer 5 friends", "icon": "share-2", "target_value": 5, "target_type": "referrals",
     "points_reward": 150, "premium_days_reward": 3, "order": 31},
    
    # Special - Gold
    {"name": "Influencer", "slug": "influencer", "category": "special", "tier": "gold",
     "description": "Refer 10 friends", "icon": "trending-up", "target_value": 10, "target_type": "referrals",
     "points_reward": 300, "premium_days_reward": 7, "order": 32},
    
    # Special - Diamond
    {"name": "Premium Pioneer", "slug": "premium_pioneer", "category": "special", "tier": "diamond",
     "description": "Subscribe to premium", "icon": "crown", "target_value": 1, "target_type": "premium_subscription",
     "points_reward": 200, "premium_days_reward": 30, "order": 33},
]


# Default point categories
DEFAULT_POINT_CATEGORIES = [
    {"name": "learning", "description": "Points earned from learning activities", "icon": "book"},
    {"name": "engagement", "description": "Points earned from engagement activities", "icon": "users"},
    {"name": "contribution", "description": "Points earned from contributing to the community", "icon": "heart"},
    {"name": "achievement", "description": "Points earned from achieving milestones", "icon": "trophy"},
]


# Default badge categories
DEFAULT_BADGE_CATEGORIES = [
    {"name": "learning", "description": "Badges for learning achievements", "icon": "book"},
    {"name": "social", "description": "Badges for social interactions", "icon": "users"},
    {"name": "streak", "description": "Badges for maintaining streaks", "icon": "fire"},
    {"name": "special", "description": "Special event badges", "icon": "star"},
]


# Default badge levels
DEFAULT_BADGE_LEVELS = [
    {"name": "bronze", "multiplier": 1.0, "icon": "bronze", "color": "#cd7f32"},
    {"name": "silver", "multiplier": 1.5, "icon": "silver", "color": "#c0c0c0"},
    {"name": "gold", "multiplier": 2.0, "icon": "gold", "color": "#ffd700"},
    {"name": "platinum", "multiplier": 3.0, "icon": "platinum", "color": "#e5e4e2"},
]


# Default point actions
DEFAULT_POINT_ACTIONS = [
    # Learning
    {"name": "complete_study_session", "category": "learning", "points": 10, "description": "Complete a study session", "max_times_per_day": 5},
    {"name": "complete_task", "category": "learning", "points": 15, "description": "Complete a task", "max_times_per_day": 10},
    {"name": "pass_quiz", "category": "learning", "points": 20, "description": "Pass a quiz", "max_times_per_day": 3},
    {"name": "submit_assignment", "category": "learning", "points": 25, "description": "Submit an assignment", "max_times_per_day": 5},
    {"name": "attend_class", "category": "learning", "points": 5, "description": "Attend a class session", "max_times_per_day": 1},
    
    # Engagement
    {"name": "daily_login", "category": "engagement", "points": 2, "description": "Log in daily", "max_times_per_day": 1},
    {"name": "post_comment", "category": "engagement", "points": 5, "description": "Post a comment", "max_times_per_day": 10},
    {"name": "like_post", "category": "engagement", "points": 1, "description": "Like a post", "max_times_per_day": 20},
    {"name": "share_content", "category": "engagement", "points": 10, "description": "Share content", "max_times_per_day": 5},
    {"name": "join_group", "category": "engagement", "points": 5, "description": "Join a group", "max_times_per_day": 1},
    
    # Contribution
    {"name": "help_peer", "category": "contribution", "points": 15, "description": "Help a peer", "max_times_per_day": 5},
    {"name": "create_content", "category": "contribution", "points": 20, "description": "Create content", "max_times_per_day": 3},
    {"name": "report_issue", "category": "contribution", "points": 10, "description": "Report an issue", "max_times_per_day": 1},
    {"name": "referral_signup", "category": "contribution", "points": 50, "description": "Refer a new user who signs up", "max_times_per_day": 10},
    {"name": "referral_subscription", "category": "contribution", "points": 100, "description": "Refer a new user who subscribes", "max_times_per_day": 10},
    
    # Achievement
    {"name": "first_task", "category": "achievement", "points": 25, "description": "Complete your first task", "max_times_per_day": 1},
    {"name": "perfect_score", "category": "achievement", "points": 50, "description": "Get a perfect score", "max_times_per_day": 1},
    {"name": "week_streak", "category": "achievement", "points": 100, "description": "Maintain a 7-day streak", "max_times_per_day": 1},
]


def create_default_gamification_data():
    """Create default gamification data."""
    # Create achievement tiers
    for tier_data in DEFAULT_ACHIEVEMENT_TIERS:
        AchievementTier.objects.get_or_create(
            name=tier_data["name"],
            defaults=tier_data,
        )

    # Create achievement categories
    for cat_data in DEFAULT_ACHIEVEMENT_CATEGORIES:
        AchievementCategory.objects.get_or_create(
            name=cat_data["name"],
            defaults=cat_data,
        )

    # Create achievements
    for achievement_data in DEFAULT_ACHIEVEMENTS:
        category_name = achievement_data.pop("category")
        tier_name = achievement_data.pop("tier")
        category = AchievementCategory.objects.filter(name=category_name).first()
        tier = AchievementTier.objects.filter(name=tier_name).first()
        if category and tier:
            Achievement.objects.get_or_create(
                slug=achievement_data["slug"],
                defaults={**achievement_data, "category": category, "tier": tier},
            )

    # Create point categories
    for cat_data in DEFAULT_POINT_CATEGORIES:
        PointCategory.objects.get_or_create(
            name=cat_data["name"],
            defaults=cat_data,
        )

    # Create badge categories
    for cat_data in DEFAULT_BADGE_CATEGORIES:
        BadgeCategory.objects.get_or_create(
            name=cat_data["name"],
            defaults=cat_data,
        )

    # Create badge levels
    for level_data in DEFAULT_BADGE_LEVELS:
        BadgeLevel.objects.get_or_create(
            name=level_data["name"],
            defaults=level_data,
        )

    # Create point actions
    for action_data in DEFAULT_POINT_ACTIONS:
        category_name = action_data.pop("category")
        category = PointCategory.objects.filter(name=category_name).first()
        if category:
            PointAction.objects.get_or_create(
                name=action_data["name"],
                defaults={**action_data, "category": category},
            )
