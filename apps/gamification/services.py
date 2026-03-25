"""
Gamification services for handling points, badges, and leaderboards.
"""

from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import User

from .models import (
    PointCategory,
    PointAction,
    UserPoints,
    UserStats,
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
    create_default_gamification_data,
)


class GamificationService:
    """Service for handling gamification operations."""

    _defaults_initialized = False

    @staticmethod
    def initialize_gamification():
        """Initialize default gamification data."""
        create_default_gamification_data()

    @staticmethod
    def ensure_defaults_initialized():
        """
        Ensure the default gamification configuration exists.
        This is safe to call multiple times (best-effort + cached per-process).
        """
        if GamificationService._defaults_initialized:
            return
        try:
            GamificationService.initialize_gamification()
        except Exception:
            # Keep runtime resilient; missing defaults should not break user flows.
            pass
        try:
            StreakService.create_default_streak_rewards()
        except Exception:
            pass
        GamificationService._defaults_initialized = True

    @staticmethod
    def initialize_user_stats(user):
        """
        Initialize gamification tables for a newly created user.
        Called from accounts signals; must never raise.
        """
        try:
            GamificationService.ensure_defaults_initialized()
            GamificationService.get_or_create_user_points(user)
            GamificationService.get_or_create_user_stats(user)
            try:
                StreakService.get_or_create_user_streak(user)
            except Exception:
                pass
            return True
        except Exception:
            return False

    @staticmethod
    def get_or_create_user_points(user):
        """Get or create the internal summary row for user points."""
        user_points, created = UserPoints.objects.get_or_create(
            user=user,
            action="__summary__",
            defaults={
                "points": 0,
                "description": "",
                "total_points": 0,
                "learning_points": 0,
                "engagement_points": 0,
                "contribution_points": 0,
                "achievement_points": 0,
                "level": 1,
            },
        )
        return user_points

    @staticmethod
    def get_or_create_user_stats(user):
        """Get or create legacy-compatible user stats."""
        stats, _ = UserStats.objects.get_or_create(
            user=user,
            defaults={
                "total_points": 0,
                "total_uploads": 0,
                "total_downloads": 0,
                "total_ratings": 0,
                "total_comments": 0,
                "total_shares": 0,
                "consecutive_login_days": 0,
                "resources_shared": 0,
                "resources_saved": 0,
            },
        )
        return stats

    @staticmethod
    def _log_points_event(user, action_name, points, description=""):
        """Persist a legacy-style points history record."""
        return UserPoints.objects.create(
            user=user,
            action=action_name if action_name in dict(UserPoints.ACTION_CHOICES) else "other",
            points=points,
            description=description or "",
        )

    @staticmethod
    def _update_all_time_leaderboard(user):
        """Keep per-user all-time leaderboard entry in sync with user stats."""
        stats = GamificationService.get_or_create_user_stats(user)
        Leaderboard.objects.update_or_create(
            user=user,
            period="all_time",
            defaults={
                "leaderboard_type": "global",
                "points": stats.total_points,
                "rank": 0,
                "snapshot_data": {},
            },
        )
        entries = list(
            Leaderboard.objects.filter(period="all_time", user__isnull=False)
            .select_related("user")
            .order_by("-points", "user_id")
        )
        for idx, entry in enumerate(entries, start=1):
            if entry.rank != idx:
                entry.rank = idx
                entry.save(update_fields=["rank", "updated_at"])

    @staticmethod
    def calculate_level(total_points):
        """Calculate user level based on total points."""
        # Level formula: level = floor(sqrt(total_points / 100)) + 1
        # Level 1: 0-99, Level 2: 100-399, Level 3: 400-899, etc.
        if total_points < 100:
            return 1
        return int((total_points / 100) ** 0.5) + 1

    @staticmethod
    def get_points_for_next_level(current_level):
        """Get points required for the next level."""
        return (current_level ** 2) * 100

    @staticmethod
    def get_points_for_level(level):
        """Get total points required to reach a level."""
        return ((level - 1) ** 2) * 100

    @staticmethod
    def can_perform_action(user, action):
        """Check if user can perform an action based on daily limits."""
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        action_count = PointTransaction.objects.filter(
            user=user,
            action=action,
            created_at__gte=today_start,
        ).count()
        
        return action_count < action.max_times_per_day

    @staticmethod
    def award_points(user, action_name, description="", reference_id="", reference_type=""):
        """
        Award points to a user for a specific action.
        Returns (success, message, points_awarded).
        """
        action = PointAction.objects.filter(name=action_name, is_active=True).first()
        if not action:
            return (False, f"Action '{action_name}' not found", 0)

        # Check daily limit
        if not GamificationService.can_perform_action(user, action):
            return (False, f"Daily limit reached for '{action_name}'", 0)

        # Get or create user points
        user_points = GamificationService.get_or_create_user_points(user)
        user_stats = GamificationService.get_or_create_user_stats(user)

        # Create transaction
        with transaction.atomic():
            # Update user points
            category_field_map = {
                "learning": "learning_points",
                "engagement": "engagement_points",
                "contribution": "contribution_points",
                "achievement": "achievement_points",
            }
            
            category_field = category_field_map.get(action.category.name, "total_points")
            
            # Update category points
            setattr(user_points, category_field, 
                    getattr(user_points, category_field) + action.points)
            
            # Update total points
            user_points.total_points += action.points
            
            # Recalculate level
            new_level = GamificationService.calculate_level(user_points.total_points)
            user_points.level = new_level
            
            user_points.save()
            user_stats.total_points += action.points
            user_stats.save(update_fields=["total_points", "updated_at"])

            # Create transaction record
            PointTransaction.objects.create(
                user=user,
                action=action,
                category=action.category,
                points=action.points,
                balance_after=user_points.total_points,
                description=description or action.description,
                reference_id=reference_id,
                reference_type=reference_type,
            )
            GamificationService._log_points_event(
                user=user,
                action_name=action_name,
                points=action.points,
                description=description or action.description,
            )

            # Check for badge eligibility
            GamificationService.check_badge_eligibility(user)
            GamificationService._update_all_time_leaderboard(user)

            return (True, f"Awarded {action.points} points", action.points)

    @staticmethod
    def award_custom_points(user, category_name, points, description="", reference_id="", reference_type=""):
        """
        Award custom points to a user (for integration with other systems).
        """
        category = PointCategory.objects.filter(name=category_name, is_active=True).first()
        if not category:
            return (False, f"Category '{category_name}' not found", 0)

        user_points = GamificationService.get_or_create_user_points(user)
        user_stats = GamificationService.get_or_create_user_stats(user)

        with transaction.atomic():
            category_field_map = {
                "learning": "learning_points",
                "engagement": "engagement_points",
                "contribution": "contribution_points",
                "achievement": "achievement_points",
            }
            
            category_field = category_field_map.get(category_name, "total_points")
            
            setattr(user_points, category_field, 
                    getattr(user_points, category_field) + points)
            user_points.total_points += points
            
            new_level = GamificationService.calculate_level(user_points.total_points)
            user_points.level = new_level
            user_points.save()
            user_stats.total_points += points
            user_stats.save(update_fields=["total_points", "updated_at"])

            PointTransaction.objects.create(
                user=user,
                category=category,
                points=points,
                balance_after=user_points.total_points,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
            )
            GamificationService._log_points_event(
                user=user,
                action_name="other",
                points=points,
                description=description,
            )

            GamificationService.check_badge_eligibility(user)
            GamificationService._update_all_time_leaderboard(user)

            return (True, f"Awarded {points} points", points)

    @staticmethod
    def get_user_points(user):
        """Get user points with breakdown."""
        user_points = GamificationService.get_or_create_user_points(user)
        
        return {
            "total_points": user_points.total_points,
            "level": user_points.level,
            "learning_points": user_points.learning_points,
            "engagement_points": user_points.engagement_points,
            "contribution_points": user_points.contribution_points,
            "achievement_points": user_points.achievement_points,
            "points_to_next_level": (
                GamificationService.get_points_for_next_level(user_points.level) 
                - user_points.total_points
            ),
            "current_level_points": (
                user_points.total_points - GamificationService.get_points_for_level(user_points.level)
            ),
            "points_for_next_level": (
                GamificationService.get_points_for_next_level(user_points.level) 
                - GamificationService.get_points_for_level(user_points.level)
            ),
        }

    @staticmethod
    def get_user_points_history(user, limit=50):
        """Get user points transaction history."""
        return UserPoints.objects.filter(user=user).exclude(action="__summary__")[:limit]

    @staticmethod
    def check_badge_eligibility(user):
        """Check if user is eligible for any badges and award them."""
        user_points = GamificationService.get_or_create_user_points(user)
        user_stats = GamificationService.get_or_create_user_stats(user)
        user_badges = UserBadge.objects.filter(user=user, is_active=True).values_list(
            "badge_id", flat=True
        )

        eligible_badges = Badge.objects.filter(is_active=True).exclude(id__in=user_badges)
        awarded_badges = []

        stats_map = {
            "total_uploads": user_stats.total_uploads,
            "total_downloads": user_stats.total_downloads,
            "total_shares": user_stats.total_shares,
            "total_comments": user_stats.total_comments,
            "total_ratings": user_stats.total_ratings,
            "resources_shared": user_stats.resources_shared,
            "resources_saved": user_stats.resources_saved,
            "consecutive_login_days": user_stats.consecutive_login_days,
            "email_verified": 1 if getattr(user, "is_verified", False) else 0,
        }

        for badge in eligible_badges:
            should_award = False

            requirement_type = (badge.requirement_type or "").strip()
            requirement_value = int(badge.requirement_value or 0)
            if requirement_type and requirement_value > 0:
                should_award = stats_map.get(requirement_type, 0) >= requirement_value

            # Check points-based badges
            if not should_award and badge.points_required > 0 and badge.points_required <= user_points.total_points:
                should_award = True

            # Check action-based badges
            if not should_award and badge.action_count_required > 0 and badge.related_action:
                action_count = PointTransaction.objects.filter(
                    user=user,
                    action=badge.related_action,
                ).count()
                if action_count >= badge.action_count_required:
                    should_award = True

            if not should_award:
                continue

            _, created = UserBadge.objects.get_or_create(
                user=user,
                badge=badge,
                defaults={"is_active": True},
            )
            if not created:
                continue
            awarded_badges.append(badge)

            badge_points = int(badge.points_required or 0)
            if badge_points > 0:
                user_points.total_points += badge_points
                user_points.achievement_points += badge_points
                user_points.level = GamificationService.calculate_level(user_points.total_points)
                user_points.save(update_fields=["total_points", "achievement_points", "level", "updated_at"])

                user_stats.total_points += badge_points
                user_stats.save(update_fields=["total_points", "updated_at"])

                achievement_category = PointCategory.objects.filter(name="achievement").first()
                if achievement_category:
                    PointTransaction.objects.create(
                        user=user,
                        action=None,
                        category=achievement_category,
                        points=badge_points,
                        balance_after=user_points.total_points,
                        description=f"Awarded badge: {badge.name}",
                        reference_id=str(badge.id),
                        reference_type="badge",
                    )
                GamificationService._log_points_event(
                    user=user,
                    action_name="earn_badge",
                    points=badge_points,
                    description=f"Earned badge: {badge.name}",
                )
                GamificationService._update_all_time_leaderboard(user)

        return awarded_badges

    @staticmethod
    def get_user_badges(user):
        """Get all badges earned by a user."""
        return UserBadge.objects.filter(
            user=user, 
            is_active=True
        ).select_related("badge__category", "badge__level")

    @staticmethod
    def get_all_badges():
        """Get all available badges."""
        return Badge.objects.filter(
            is_active=True
        ).select_related("category", "level")

    @staticmethod
    def get_user_badge_progress(user):
        """Get progress towards unearned badges."""
        user_points = GamificationService.get_or_create_user_points(user)
        user_badges = UserBadge.objects.filter(user=user, is_active=True).values_list(
            "badge_id", flat=True
        )
        
        available_badges = Badge.objects.filter(
            is_active=True
        ).exclude(id__in=user_badges).select_related("category", "level")
        
        progress = []
        for badge in available_badges:
            if badge.points_required > 0:
                progress_percent = min(
                    100, 
                    (user_points.total_points / badge.points_required) * 100
                )
            else:
                progress_percent = 0
                
            progress.append({
                "badge": {
                    "id": str(badge.id),
                    "name": badge.name,
                    "slug": badge.slug,
                    "description": badge.description,
                    "icon": badge.icon,
                    "category": badge.category.name,
                    "level": badge.level.name,
                },
                "progress_percent": progress_percent,
                "points_required": badge.points_required,
                "current_points": user_points.total_points,
            })
        
        return progress

    # ============== Event Hooks (called by other apps) ==============

    @staticmethod
    def _ensure_point_action(action_name, category_name, points, description, max_times_per_day=20):
        category, _ = PointCategory.objects.get_or_create(
            name=category_name,
            defaults={"description": "", "icon": "", "is_active": True},
        )
        action, _ = PointAction.objects.get_or_create(
            name=action_name,
            defaults={
                "category": category,
                "points": points,
                "description": description,
                "max_times_per_day": max_times_per_day,
                "is_active": True,
            },
        )
        return action

    @staticmethod
    def _safe_record_streak_activity(user, points_earned=0, activity_count=1):
        try:
            StreakService.record_activity(
                user=user,
                activity_count=activity_count,
                points_earned=points_earned or 0,
            )
        except Exception:
            pass

    @staticmethod
    def record_login(user):
        """Record a daily login (points + streak activity)."""
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="daily_login",
            category_name="engagement",
            points=5,
            description="Daily login",
            max_times_per_day=1,
        )
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="daily_login",
            description="Daily login",
            reference_id=str(timezone.now().date()),
            reference_type="daily_login",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            today = timezone.now().date()
            if stats.last_login_date != today:
                if stats.last_login_date == today - timedelta(days=1):
                    stats.consecutive_login_days += 1
                else:
                    stats.consecutive_login_days = 1
                stats.last_login_date = today
                stats.save(update_fields=["consecutive_login_days", "last_login_date", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_email_verification(user):
        """Record email verification once per user."""
        GamificationService.ensure_defaults_initialized()
        if UserPoints.objects.filter(user=user, action="verify_email").exists():
            return {"success": True, "message": "Already recorded", "points": 0}

        GamificationService._ensure_point_action(
            action_name="verify_email",
            category_name="achievement",
            points=4,
            description="Verified email address",
            max_times_per_day=1,
        )
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="verify_email",
            description="Verified email address",
            reference_id=str(getattr(user, "id", "") or ""),
            reference_type="email_verification",
        )
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_upload(user, resource=None):
        """Record a resource upload."""
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="upload_resource",
            category_name="contribution",
            points=10,
            description="Uploaded a resource",
            max_times_per_day=50,
        )
        reference_id = str(getattr(resource, "id", "") or "")
        description = "Uploaded a resource"
        title = getattr(resource, "title", None)
        if title:
            description = f'Uploaded resource: "{title}"'
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="upload_resource",
            description=description,
            reference_id=reference_id,
            reference_type="resource_upload",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            stats.total_uploads += 1
            stats.save(update_fields=["total_uploads", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_share(user, resource=None):
        """Record a share event."""
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="share_resource",
            category_name="engagement",
            points=8,
            description="Shared content",
            max_times_per_day=100,
        )
        reference_id = str(getattr(resource, "id", "") or "")
        description = "Shared content"
        title = getattr(resource, "title", None)
        if title:
            description = f'Shared resource: "{title}"'
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="share_resource",
            description=description,
            reference_id=reference_id,
            reference_type="resource_share",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            stats.total_shares += 1
            stats.resources_shared += 1
            stats.save(update_fields=["total_shares", "resources_shared", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_comment(user, comment=None):
        """Record a comment event."""
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="comment_resource",
            category_name="engagement",
            points=3,
            description="Posted a comment",
            max_times_per_day=100,
        )
        reference_id = str(getattr(comment, "id", "") or "")
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="comment_resource",
            description="Posted a comment",
            reference_id=reference_id,
            reference_type="comment",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            stats.total_comments += 1
            stats.save(update_fields=["total_comments", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_rating(user, rating=None):
        """Record a rating event."""
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="rate_resource",
            category_name="engagement",
            points=2,
            description="Rated a resource",
            max_times_per_day=100,
        )
        reference_id = str(getattr(rating, "id", "") or "")
        success, message, points = GamificationService.award_points(
            user=user,
            action_name="rate_resource",
            description="Rated a resource",
            reference_id=reference_id,
            reference_type="rating",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            stats.total_ratings += 1
            stats.save(update_fields=["total_ratings", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def record_download(user, resource=None, personal_file=None):
        """
        Record a download event.
        The default point actions don't include downloads, so we lazily create
        a small learning action with a sane daily cap.
        """
        GamificationService.ensure_defaults_initialized()
        GamificationService._ensure_point_action(
            action_name="download_resource",
            category_name="learning",
            points=2,
            description="Downloaded a resource",
            max_times_per_day=200,
        )

        reference_id = str(getattr(resource, "id", "") or getattr(personal_file, "id", "") or "")
        # Bucket by day to keep reference IDs meaningful for analytics/debugging.
        reference_suffix = str(timezone.now().date())
        reference_id = f"{reference_id}:{reference_suffix}" if reference_id else reference_suffix

        success, message, points = GamificationService.award_points(
            user=user,
            action_name="download_resource",
            description="Downloaded a resource",
            reference_id=reference_id,
            reference_type="download",
        )
        if success:
            stats = GamificationService.get_or_create_user_stats(user)
            stats.total_downloads += 1
            stats.save(update_fields=["total_downloads", "updated_at"])
        GamificationService._safe_record_streak_activity(user, points_earned=points, activity_count=1)
        return {"success": success, "message": message, "points": points}

    @staticmethod
    def sync_saved_resources_count(user):
        """Sync bookmark-backed saved-resource counter."""
        stats = GamificationService.get_or_create_user_stats(user)
        try:
            from apps.bookmarks.models import Bookmark
            stats.resources_saved = Bookmark.objects.filter(user=user).count()
            stats.save(update_fields=["resources_saved", "updated_at"])
        except Exception:
            pass


class LeaderboardService:
    """Service for handling leaderboard operations."""

    @staticmethod
    def get_leaderboard(leaderboard_type="global", period="all_time", faculty_id=None, department_id=None, limit=100):
        """
        Get leaderboard data.
        
        Args:
            leaderboard_type: 'global', 'faculty', or 'department'
            period: 'daily', 'weekly', 'monthly', or 'all_time'
            faculty_id: Faculty ID for faculty leaderboard
            department_id: Department ID for department leaderboard
            limit: Maximum number of users to return
        """
        # Calculate date range based on period
        now = timezone.now()
        if period == "daily":
            start_date = now - timedelta(days=1)
        elif period == "weekly":
            start_date = now - timedelta(days=7)
        elif period == "monthly":
            start_date = now - timedelta(days=30)
        else:  # all_time
            start_date = None

        # Build query
        users = User.objects.filter(is_active=True, is_deleted=False)
        
        # Filter by faculty/department
        if leaderboard_type == "faculty" and faculty_id:
            users = users.filter(faculty_id=faculty_id)
        elif leaderboard_type == "department" and department_id:
            users = users.filter(department_id=department_id)

        # Get points with optional date filter
        if start_date:
            # For period-based leaderboards, sum points from transactions in a single DB query.
            users_with_points = (
                users.select_related("faculty", "department")
                .annotate(
                    points_total=Coalesce(
                        Sum(
                            "point_transactions__points",
                            filter=Q(point_transactions__created_at__gte=start_date),
                        ),
                        0,
                    )
                )
                .order_by("-points_total", "id")[:limit]
            )

            leaderboard_data = []
            for rank, user in enumerate(users_with_points, 1):
                points = int(getattr(user, "points_total", 0) or 0)
                leaderboard_data.append({
                    "rank": rank,
                    "user_id": str(user.id),
                    "user_name": user.full_name or user.email,
                    "user_email": user.email,
                    "profile_image": user.profile_image.url if user.profile_image else None,
                    "faculty": user.faculty.name if user.faculty else None,
                    "department": user.department.name if user.department else None,
                    "points": points,
                })
        else:
            user_points = UserStats.objects.filter(
                user__in=users
            ).select_related("user__faculty", "user__department").order_by("-total_points")[:limit]

            leaderboard_data = []
            for rank, up in enumerate(user_points, 1):
                leaderboard_data.append({
                    "rank": rank,
                    "user_id": str(up.user.id),
                    "user_name": up.user.full_name or up.user.email,
                    "user_email": up.user.email,
                    "profile_image": up.user.profile_image.url if up.user.profile_image else None,
                    "faculty": up.user.faculty.name if up.user.faculty else None,
                    "department": up.user.department.name if up.user.department else None,
                    "points": up.total_points,
                    "level": GamificationService.calculate_level(up.total_points),
                })

        return leaderboard_data

    @staticmethod
    def get_user_rank(user, leaderboard_type="global", period="all_time"):
        """Get user's rank in the leaderboard."""
        leaderboard = LeaderboardService.get_leaderboard(
            leaderboard_type=leaderboard_type,
            period=period,
        )
        
        for entry in leaderboard:
            if entry["user_id"] == str(user.id):
                return entry
        
        return None

    @staticmethod
    def save_leaderboard_snapshot(leaderboard_type, period, faculty_id=None, department_id=None):
        """Save a leaderboard snapshot for historical data."""
        data = LeaderboardService.get_leaderboard(
            leaderboard_type=leaderboard_type,
            period=period,
            faculty_id=faculty_id,
            department_id=department_id,
        )
        
        leaderboard = Leaderboard.objects.create(
            leaderboard_type=leaderboard_type,
            period=period,
            faculty_id=faculty_id,
            department_id=department_id,
            snapshot_data=data,
        )
        
        return leaderboard


# Import transaction for atomic operations
from django.db import transaction


class ReferralIntegration:
    """Integration between referral system and gamification."""

    @staticmethod
    def sync_referral_points(user, points, referral_email):
        """
        Sync referral points to gamification system.
        Called when referral rewards are awarded.
        """
        return GamificationService.award_custom_points(
            user=user,
            category_name="contribution",
            points=points,
            description=f"Referral signup: {referral_email}",
            reference_id=referral_email,
            reference_type="referral",
        )

    @staticmethod
    def sync_referral_subscription(user, points, referral_email):
        """
        Sync referral subscription rewards to gamification system.
        Called when a referral subscribes.
        """
        return GamificationService.award_custom_points(
            user=user,
            category_name="contribution",
            points=points,
            description=f"Referral subscription: {referral_email}",
            reference_id=referral_email,
            reference_type="referral_subscription",
        )


class StreakService:
    """Service for handling daily engagement streaks."""

    # Activity threshold - minimum activities needed to maintain streak
    ACTIVITY_THRESHOLD = 3
    
    # Grace period in hours for timezone differences
    GRACE_PERIOD_HOURS = 36
    
    # Streak milestones
    STREAK_MILESTONES = [7, 30, 100]
    
    # Reward amounts
    STREAK_REWARDS = {
        7: {"points": 50, "badge_slug": "week_streak"},
        30: {"points": 200, "badge_slug": "month_streak"},
        100: {"points": 500, "badge_slug": "century_streak"},
    }

    @staticmethod
    def get_or_create_user_streak(user):
        """Get or create user streak record."""
        user_streak, created = UserStreak.objects.get_or_create(
            user=user,
            defaults={
                "current_streak": 0,
                "longest_streak": 0,
                "streak_freezes": 1,
                "is_frozen": False,
            },
        )
        return user_streak

    @staticmethod
    def record_activity(user, activity_count=1, points_earned=0):
        """
        Record user activity and update streak.
        Returns (streak_data, milestone_reached).
        """
        from django.db import transaction
        from django.utils import timezone
        from django.db.models import Sum

        with transaction.atomic():
            # Get or create user streak
            user_streak = StreakService.get_or_create_user_streak(user)
            
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            # Check if streak is frozen
            if user_streak.is_frozen:
                # Unfreeze if enough time has passed or if it's been a day
                if user_streak.freeze_start_date:
                    days_frozen = (today - user_streak.freeze_start_date).days
                    if days_frozen >= 1:
                        user_streak.is_frozen = False
                        user_streak.freeze_start_date = None
                        user_streak.save()
                
                # Still record activity but don't increment streak
                StreakService._record_history(
                    user, today, activity_count, points_earned, user_streak.current_streak
                )
                return (user_streak, None)
            
            # Check if user already recorded activity today
            existing_history = StreakHistory.objects.filter(
                user=user, date=today
            ).first()
            
            if existing_history:
                # Update existing record
                existing_history.activity_count += activity_count
                existing_history.points_earned += points_earned
                existing_history.save()
                return (user_streak, None)
            
            # Calculate streak
            new_streak = user_streak.current_streak
            milestone_reached = None
            
            if user_streak.last_activity_date is None:
                # First activity
                new_streak = 1
            elif user_streak.last_activity_date == yesterday:
                # Consecutive day
                new_streak = user_streak.current_streak + 1
            elif user_streak.last_activity_date == today:
                # Already recorded today
                pass
            else:
                # Check grace period
                days_diff = (today - user_streak.last_activity_date).days
                if days_diff <= 1:
                    # Within grace period, maintain streak
                    new_streak = user_streak.current_streak
                else:
                    # Streak broken, start fresh
                    new_streak = 1
            
            # Check if activity threshold is met
            total_today_activity = activity_count
            if existing_history:
                total_today_activity += existing_history.activity_count
            
            if total_today_activity >= StreakService.ACTIVITY_THRESHOLD:
                # Update streak
                user_streak.current_streak = new_streak
                user_streak.last_activity_date = today
                
                # Update longest streak
                if new_streak > user_streak.longest_streak:
                    user_streak.longest_streak = new_streak
                
                user_streak.save()
                
                # Check for milestone
                if new_streak in StreakService.STREAK_MILESTONES:
                    milestone_reached = new_streak
                    # Award rewards
                    StreakService._award_streak_reward(user, new_streak)
            
            # Record history
            StreakService._record_history(
                user, today, activity_count, points_earned, user_streak.current_streak, milestone_reached
            )
            
            return (user_streak, milestone_reached)

    @staticmethod
    def _record_history(user, date, activity_count, points_earned, streak_at_date, milestone_reached=None):
        """Record streak history entry."""
        history, created = StreakHistory.objects.get_or_create(
            user=user,
            date=date,
            defaults={
                "activity_count": activity_count,
                "points_earned": points_earned,
                "streak_at_date": streak_at_date,
                "milestone_reached": str(milestone_reached) if milestone_reached else "",
            },
        )
        if not created:
            history.activity_count += activity_count
            history.points_earned += points_earned
            history.streak_at_date = streak_at_date
            if milestone_reached:
                history.milestone_reached = str(milestone_reached)
            history.save()
        return history

    @staticmethod
    def _award_streak_reward(user, milestone):
        """Award rewards for reaching a streak milestone."""
        reward_data = StreakService.STREAK_REWARDS.get(milestone)
        if not reward_data:
            return
        
        # Award points
        if reward_data.get("points"):
            GamificationService.award_custom_points(
                user=user,
                category_name="engagement",
                points=reward_data["points"],
                description=f"{milestone}-day streak reward",
                reference_type="streak_reward",
            )
        
        # Award badge
        if reward_data.get("badge_slug"):
            badge = Badge.objects.filter(slug=reward_data["badge_slug"]).first()
            if badge:
                UserBadge.objects.get_or_create(
                    user=user,
                    badge=badge,
                )

    @staticmethod
    def activate_streak_freeze(user):
        """
        Activate streak freeze (pauses streak for 1 day).
        Returns (success, message).
        """
        user_streak = StreakService.get_or_create_user_streak(user)
        
        if user_streak.streak_freezes <= 0:
            return (False, "No streak freezes available")
        
        if user_streak.is_frozen:
            return (False, "Streak is already frozen")
        
        user_streak.is_frozen = True
        user_streak.freeze_start_date = timezone.now().date()
        user_streak.streak_freezes -= 1
        user_streak.save()
        
        return (True, "Streak frozen successfully")

    @staticmethod
    def deactivate_streak_freeze(user):
        """Deactivate streak freeze."""
        user_streak = UserStreak.objects.filter(user=user).first()
        
        if not user_streak or not user_streak.is_frozen:
            return (False, "Streak is not frozen")
        
        user_streak.is_frozen = False
        user_streak.freeze_start_date = None
        user_streak.save()
        
        return (True, "Streak unfrozen successfully")

    @staticmethod
    def get_streak_status(user):
        """Get current streak status for user."""
        user_streak = StreakService.get_or_create_user_streak(user)
        
        # Calculate days until next milestone
        next_milestone = None
        for milestone in StreakService.STREAK_MILESTONES:
            if milestone > user_streak.current_streak:
                next_milestone = milestone
                break
        
        days_until_next = 0
        if next_milestone:
            days_until_next = next_milestone - user_streak.current_streak
        
        return {
            "current_streak": user_streak.current_streak,
            "longest_streak": user_streak.longest_streak,
            "last_activity_date": user_streak.last_activity_date,
            "is_frozen": user_streak.is_frozen,
            "streak_freezes_remaining": user_streak.streak_freezes,
            "next_milestone": next_milestone,
            "days_until_next_milestone": days_until_next,
            "activity_threshold": StreakService.ACTIVITY_THRESHOLD,
        }

    @staticmethod
    def get_streak_history(user, limit=30):
        """Get user's streak history."""
        return StreakHistory.objects.filter(
            user=user
        ).order_by("-date")[:limit]

    @staticmethod
    def check_and_update_streaks():
        """
        Check and update streaks for all users.
        Called daily via cron or scheduled task.
        """
        from django.utils import timezone
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get all users with active streaks
        user_streaks = UserStreak.objects.filter(
            current_streak__gt=0,
            is_frozen=False,
        )
        
        for user_streak in user_streaks:
            if user_streak.last_activity_date is None:
                continue
            
            # Check if user missed yesterday
            if user_streak.last_activity_date < yesterday:
                # Check grace period
                days_missed = (today - user_streak.last_activity_date).days
                
                if days_missed > 1:
                    # Streak broken
                    user_streak.current_streak = 0
                    user_streak.save()
        
        return True

    @staticmethod
    def create_default_streak_rewards():
        """Create default streak reward configurations."""
        streak_rewards = [
            {
                "streak_milestone": 7,
                "reward_type": "both",
                "bonus_points": 50,
            },
            {
                "streak_milestone": 30,
                "reward_type": "both",
                "bonus_points": 200,
            },
            {
                "streak_milestone": 100,
                "reward_type": "both",
                "bonus_points": 500,
            },
        ]
        
        for reward_data in streak_rewards:
            StreakReward.objects.get_or_create(
                streak_milestone=reward_data["streak_milestone"],
                defaults=reward_data,
            )


class AchievementService:
    """Service for handling achievement milestones."""

    @staticmethod
    def get_all_achievements(category=None, tier=None, is_featured=None):
        """
        Get all achievements with optional filtering.
        
        Args:
            category: Filter by category name
            tier: Filter by tier name
            is_featured: Filter by featured status
        """
        queryset = Achievement.objects.filter(is_active=True)
        
        if category:
            queryset = queryset.filter(category__name=category)
        if tier:
            queryset = queryset.filter(tier__name=tier)
        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured)
            
        return queryset.select_related("category", "tier", "badge").order_by("tier", "order")

    @staticmethod
    def get_achievement_by_id(achievement_id):
        """Get achievement by ID."""
        try:
            return Achievement.objects.select_related("category", "tier", "badge").get(
                id=achievement_id,
                is_active=True,
            )
        except Achievement.DoesNotExist:
            return None

    @staticmethod
    def get_achievement_by_slug(slug):
        """Get achievement by slug."""
        try:
            return Achievement.objects.select_related("category", "tier", "badge").get(
                slug=slug,
                is_active=True,
            )
        except Achievement.DoesNotExist:
            return None

    @staticmethod
    def get_user_achievements(user, include_completed=True, include_in_progress=True):
        """
        Get user's achievements with progress.
        
        Args:
            user: User instance
            include_completed: Include completed achievements
            include_in_progress: Include in-progress achievements
        """
        user_achievements = UserAchievement.objects.filter(user=user)
        
        if not include_completed:
            user_achievements = user_achievements.filter(is_completed=False)
        if not include_in_progress:
            user_achievements = user_achievements.filter(is_completed=True)
            
        return user_achievements.select_related(
            "achievement__category",
            "achievement__tier",
            "achievement__badge",
        ).order_by("-is_completed", "-completed_at", "achievement__order")

    @staticmethod
    def get_achievement_progress(user, achievement_id):
        """
        Get user's progress for a specific achievement.
        
        Returns dict with progress details or None if achievement doesn't exist.
        """
        achievement = AchievementService.get_achievement_by_id(achievement_id)
        if not achievement:
            return None
            
        user_achievement, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={"current_progress": 0},
        )
        
        progress_percent = user_achievement.progress_percent
        remaining = max(0, achievement.target_value - user_achievement.current_progress)
        
        return {
            "achievement": {
                "id": str(achievement.id),
                "name": achievement.name,
                "slug": achievement.slug,
                "description": achievement.description,
                "icon": achievement.icon,
                "category": achievement.category.name,
                "tier": achievement.tier.name,
                "target_value": achievement.target_value,
                "target_type": achievement.target_type,
                "points_reward": achievement.points_reward,
                "premium_days_reward": achievement.premium_days_reward,
                "badge_id": str(achievement.badge.id) if achievement.badge else None,
                "badge_name": achievement.badge.name if achievement.badge else None,
                "profile_customization": achievement.profile_customization,
            },
            "user_progress": {
                "current_progress": user_achievement.current_progress,
                "target_value": achievement.target_value,
                "progress_percent": progress_percent,
                "remaining": remaining,
                "is_completed": user_achievement.is_completed,
                "completed_at": user_achievement.completed_at,
                "is_reward_claimed": user_achievement.is_reward_claimed,
                "claimed_at": user_achievement.claimed_at,
            },
        }

    @staticmethod
    def update_achievement_progress(user, target_type, increment=1):
        """
        Update achievement progress for a user based on target type.
        
        Args:
            user: User instance
            target_type: Type of target (e.g., 'courses_completed', 'streak_days')
            increment: Amount to increment progress by
            
        Returns list of newly completed achievements.
        """
        # Get all active achievements for this target type
        achievements = Achievement.objects.filter(
            target_type=target_type,
            is_active=True,
        ).select_related("category", "tier")
        
        newly_completed = []
        
        for achievement in achievements:
            # Get or create user achievement
            user_achievement, created = UserAchievement.objects.get_or_create(
                user=user,
                achievement=achievement,
                defaults={"current_progress": 0},
            )
            
            # Skip if already completed
            if user_achievement.is_completed:
                continue
            
            # Update progress
            user_achievement.current_progress += increment
            
            # Check if completed
            if user_achievement.current_progress >= achievement.target_value:
                user_achievement.is_completed = True
                user_achievement.completed_at = timezone.now()
                newly_completed.append({
                    "achievement": achievement,
                    "user_achievement": user_achievement,
                })
            
            user_achievement.save()
        
        return newly_completed

    @staticmethod
    def set_achievement_progress(user, target_type, value):
        """
        Set achievement progress for a user to a specific value.
        Used when syncing progress from other systems.
        
        Args:
            user: User instance
            target_type: Type of target
            value: New progress value
            
        Returns list of newly completed achievements.
        """
        achievements = Achievement.objects.filter(
            target_type=target_type,
            is_active=True,
        ).select_related("category", "tier")
        
        newly_completed = []
        
        for achievement in achievements:
            user_achievement, created = UserAchievement.objects.get_or_create(
                user=user,
                achievement=achievement,
                defaults={"current_progress": 0},
            )
            
            if user_achievement.is_completed:
                continue
            
            user_achievement.current_progress = value
            
            if user_achievement.current_progress >= achievement.target_value:
                user_achievement.is_completed = True
                user_achievement.completed_at = timezone.now()
                newly_completed.append({
                    "achievement": achievement,
                    "user_achievement": user_achievement,
                })
            
            user_achievement.save()
        
        return newly_completed

    @staticmethod
    def claim_achievement_reward(user, achievement_id):
        """
        Claim reward for a completed achievement.
        
        Args:
            user: User instance
            achievement_id: Achievement ID
            
        Returns (success, message, rewards_dict)
        """
        achievement = AchievementService.get_achievement_by_id(achievement_id)
        if not achievement:
            return (False, "Achievement not found", {})
        
        try:
            user_achievement = UserAchievement.objects.get(
                user=user,
                achievement=achievement,
            )
        except UserAchievement.DoesNotExist:
            return (False, "User achievement not found", {})
        
        if not user_achievement.is_completed:
            return (False, "Achievement not completed yet", {})
        
        if user_achievement.is_reward_claimed:
            return (False, "Reward already claimed", {})
        
        # Process rewards
        rewards = {
            "points": 0,
            "premium_days": 0,
            "badge": None,
            "profile_customization": None,
        }
        
        # Award points
        if achievement.points_reward > 0:
            success, message, points = GamificationService.award_custom_points(
                user=user,
                category_name="achievement",
                points=achievement.points_reward,
                description=f"Achievement completed: {achievement.name}",
                reference_id=str(achievement.id),
                reference_type="achievement",
            )
            if success:
                rewards["points"] = achievement.points_reward
        
        # Award premium days (would integrate with payments system)
        if achievement.premium_days_reward > 0:
            # TODO: Integrate with payments system to add premium days
            rewards["premium_days"] = achievement.premium_days_reward
        
        # Award badge
        if achievement.badge:
            UserBadge.objects.get_or_create(
                user=user,
                badge=achievement.badge,
                defaults={"is_active": True},
            )
            rewards["badge"] = {
                "id": str(achievement.badge.id),
                "name": achievement.badge.name,
            }
        
        # Set profile customization
        if achievement.profile_customization:
            rewards["profile_customization"] = achievement.profile_customization
        
        # Mark reward as claimed
        user_achievement.is_reward_claimed = True
        user_achievement.claimed_at = timezone.now()
        user_achievement.save()
        
        return (True, "Reward claimed successfully", rewards)

    @staticmethod
    def get_user_achievement_stats(user):
        """Get user's achievement statistics."""
        user_achievements = UserAchievement.objects.filter(user=user)
        
        total_achievements = Achievement.objects.filter(is_active=True).count()
        completed = user_achievements.filter(is_completed=True).count()
        in_progress = user_achievements.filter(is_completed=False, current_progress__gt=0).count()
        rewards_claimed = user_achievements.filter(is_reward_claimed=True).count()
        
        # Points earned from achievements
        points_earned = sum(
            ua.achievement.points_reward 
            for ua in user_achievements.filter(is_completed=True)
        )
        
        return {
            "total_achievements": total_achievements,
            "completed": completed,
            "in_progress": in_progress,
            "rewards_claimed": rewards_claimed,
            "completion_percent": (completed / total_achievements * 100) if total_achievements > 0 else 0,
            "points_earned": points_earned,
        }

    @staticmethod
    def get_achievements_by_category(user=None):
        """Get achievements grouped by category."""
        achievements = Achievement.objects.filter(
            is_active=True
        ).select_related("category", "tier", "badge").order_by("category", "tier", "order")
        
        result = {}
        for achievement in achievements:
            category = achievement.category.name
            if category not in result:
                result[category] = {
                    "category": achievement.category.name,
                    "display_name": achievement.category.get_name_display(),
                    "icon": achievement.category.icon,
                    "achievements": [],
                }
            
            achievement_data = {
                "id": str(achievement.id),
                "name": achievement.name,
                "slug": achievement.slug,
                "description": achievement.description,
                "icon": achievement.icon,
                "tier": achievement.tier.name,
                "target_value": achievement.target_value,
                "target_type": achievement.target_type,
                "points_reward": achievement.points_reward,
                "premium_days_reward": achievement.premium_days_reward,
            }
            
            # Add user progress if user provided
            if user:
                try:
                    user_achievement = UserAchievement.objects.get(user=user, achievement=achievement)
                    achievement_data["user_progress"] = {
                        "current_progress": user_achievement.current_progress,
                        "is_completed": user_achievement.is_completed,
                        "is_reward_claimed": user_achievement.is_reward_claimed,
                        "progress_percent": user_achievement.progress_percent,
                    }
                except UserAchievement.DoesNotExist:
                    achievement_data["user_progress"] = {
                        "current_progress": 0,
                        "is_completed": False,
                        "is_reward_claimed": False,
                        "progress_percent": 0,
                    }
            
            result[category]["achievements"].append(achievement_data)
        
        return list(result.values())
