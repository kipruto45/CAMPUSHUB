"""
Gamification models for CampusHub.
Includes badges, points, and achievements.
"""

from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import TimeStampedModel

User = get_user_model()


def _user_label(user) -> str:
    """Return a stable human-readable label for a user."""
    if hasattr(user, "get_full_name"):
        full_name = (user.get_full_name() or "").strip()
        if full_name:
            return full_name
    return getattr(user, "email", "") or f"user:{getattr(user, 'id', 'unknown')}"


class Badge(TimeStampedModel):
    """
    Model for achievement badges.
    """

    CATEGORY_CHOICES = [
        ("uploads", "Uploads"),
        ("downloads", "Downloads"),
        ("engagement", "Engagement"),
        ("social", "Social"),
        ("learning", "Learning"),
        ("special", "Special"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # Font Awesome icon name
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    points_required = models.IntegerField(default=0)
    requirement_type = models.CharField(
        max_length=50
    )  # e.g., 'total_uploads', 'total_downloads'
    requirement_value = models.IntegerField(default=0)  # e.g., 10 uploads
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "gamification"
        ordering = ["category", "points_required"]

    def __str__(self):
        return self.name


class UserBadge(TimeStampedModel):
    """
    Model for user-earned badges.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="earned_by")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "gamification"
        unique_together = ["user", "badge"]
        ordering = ["-earned_at"]

    def __str__(self):
        return f"{_user_label(self.user)} earned {self.badge.name}"


class UserPoints(TimeStampedModel):
    """
    Model for tracking user points.
    """

    ACTION_CHOICES = [
        ("upload_resource", "Upload Resource"),
        ("download_resource", "Download Resource"),
        ("rate_resource", "Rate Resource"),
        ("comment_resource", "Comment Resource"),
        ("complete_profile", "Complete Profile"),
        ("daily_login", "Daily Login"),
        ("share_resource", "Share Resource"),
        ("report_content", "Report Content"),
        ("verify_email", "Verify Email"),
        ("first_upload", "First Upload"),
        ("first_download", "First Download"),
        ("referral", "Referral"),
        ("earn_badge", "Earn Badge"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="points_history"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    points = models.IntegerField()
    description = models.TextField(blank=True)

    class Meta:
        app_label = "gamification"
        verbose_name_plural = "User Points"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{_user_label(self.user)}: {self.action} (+{self.points})"


class UserStats(models.Model):
    """
    Model for aggregated user statistics.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="gamification_stats"
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

    class Meta:
        app_label = "gamification"
        verbose_name = "User Stats"
        verbose_name_plural = "User Stats"

    def __str__(self):
        return f"Stats for {_user_label(self.user)}: {self.total_points} points"

    def add_points(self, action: str, points: int, description: str = ""):
        """Add points and create history entry."""
        self.total_points += points
        self.save()

        UserPoints.objects.create(
            user=self.user, action=action, points=points, description=description
        )

    def update_stat(self, stat_name: str, increment: int = 1):
        """Update a specific stat."""
        if hasattr(self, stat_name):
            current = getattr(self, stat_name, 0)
            setattr(self, stat_name, current + increment)
            self.save()


class Achievement(TimeStampedModel):
    """
    Model for special achievements/milestones.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="achievements"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    points_earned = models.IntegerField(default=0)
    milestone_type = models.CharField(
        max_length=50
    )  # e.g., 'streak_30_days', '100_uploads'

    class Meta:
        app_label = "gamification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{_user_label(self.user)}: {self.title}"


class Leaderboard(models.Model):
    """
    Model for leaderboard tracking.
    """

    PERIOD_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("all_time", "All Time"),
    ]

    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="leaderboard_rankings"
    )
    rank = models.IntegerField()
    points = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "gamification"
        unique_together = ["period", "user"]
        ordering = ["period", "rank"]

    def __str__(self):
        return f"{self.period} #{self.rank}: {_user_label(self.user)} ({self.points} pts)"


# Badge definitions
DEFAULT_BADGES = [
    {
        "name": "First Steps",
        "slug": "first-steps",
        "description": "Upload your first resource",
        "icon": "fa-rocket",
        "category": "uploads",
        "points_required": 10,
        "requirement_type": "total_uploads",
        "requirement_value": 1,
    },
    {
        "name": "Contributor",
        "slug": "contributor",
        "description": "Upload 10 resources",
        "icon": "fa-upload",
        "category": "uploads",
        "points_required": 50,
        "requirement_type": "total_uploads",
        "requirement_value": 10,
    },
    {
        "name": "Prolific Uploader",
        "slug": "prolific-uploader",
        "description": "Upload 50 resources",
        "icon": "fa-trophy",
        "category": "uploads",
        "points_required": 200,
        "requirement_type": "total_uploads",
        "requirement_value": 50,
    },
    {
        "name": "First Download",
        "slug": "first-download",
        "description": "Download your first resource",
        "icon": "fa-download",
        "category": "downloads",
        "points_required": 5,
        "requirement_type": "total_downloads",
        "requirement_value": 1,
    },
    {
        "name": "Regular User",
        "slug": "regular-user",
        "description": "Download 25 resources",
        "icon": "fa-file-archive",
        "category": "downloads",
        "points_required": 75,
        "requirement_type": "total_downloads",
        "requirement_value": 25,
    },
    {
        "name": "Knowledge Seeker",
        "slug": "knowledge-seeker",
        "description": "Download 100 resources",
        "icon": "fa-graduation-cap",
        "category": "downloads",
        "points_required": 250,
        "requirement_type": "total_downloads",
        "requirement_value": 100,
    },
    {
        "name": "Critic",
        "slug": "critic",
        "description": "Rate 10 resources",
        "icon": "fa-star",
        "category": "engagement",
        "points_required": 25,
        "requirement_type": "total_ratings",
        "requirement_value": 10,
    },
    {
        "name": "Commentator",
        "slug": "commentator",
        "description": "Leave 25 comments",
        "icon": "fa-comments",
        "category": "engagement",
        "points_required": 50,
        "requirement_type": "total_comments",
        "requirement_value": 25,
    },
    {
        "name": "Social Butterfly",
        "slug": "social-butterfly",
        "description": "Make 10 friends",
        "icon": "fa-users",
        "category": "social",
        "points_required": 30,
        "requirement_type": "total_friends",
        "requirement_value": 10,
    },
    {
        "name": "Verified",
        "slug": "verified",
        "description": "Verify your email address",
        "icon": "fa-check-circle",
        "category": "special",
        "points_required": 15,
        "requirement_type": "email_verified",
        "requirement_value": 1,
    },
    {
        "name": "Consistent Learner",
        "slug": "consistent-learner",
        "description": "Login for 7 consecutive days",
        "icon": "fa-fire",
        "category": "special",
        "points_required": 35,
        "requirement_type": "consecutive_login_days",
        "requirement_value": 7,
    },
]
