"""Service layer for gamification statistics, badges, and leaderboards."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Achievement, Badge, Leaderboard, UserBadge, UserStats


class GamificationService:
    """Encapsulate gamification business logic for views and automations."""

    SUPPORTED_PERIODS = {"daily", "weekly", "monthly", "all_time"}
    POINT_VALUES = {
        "upload_resource": 10,
        "download_resource": 3,
        "rate_resource": 2,
        "comment_resource": 2,
        "daily_login": 1,
        "share_resource": 5,
        "verify_email": 15,
    }

    PROGRESS_FIELDS = {
        "total_uploads": "total_uploads",
        "total_downloads": "total_downloads",
        "total_ratings": "total_ratings",
        "total_comments": "total_comments",
        "total_shares": "total_shares",
        "consecutive_login_days": "consecutive_login_days",
        "email_verified": "email_verified",
    }

    @classmethod
    def get_or_create_stats(cls, user) -> UserStats:
        stats, _ = UserStats.objects.get_or_create(user=user)
        return stats

    @staticmethod
    def _should_track_user(user) -> bool:
        return bool(user and getattr(user, "is_authenticated", True))

    @classmethod
    def initialize_user_stats(cls, user) -> UserStats:
        """Ensure the user has a stats row ready for later automations."""
        return cls.get_or_create_stats(user)

    @classmethod
    def normalize_period(cls, period: str | None) -> str:
        normalized = str(period or "all_time").strip().lower()
        return normalized if normalized in cls.SUPPORTED_PERIODS else "all_time"

    @classmethod
    def get_progress_value(cls, *, user, stats: UserStats, badge: Badge) -> int:
        if badge.requirement_type == "email_verified":
            return 1 if user.is_verified else 0
        field_name = cls.PROGRESS_FIELDS.get(badge.requirement_type)
        if not field_name:
            return 0
        return int(getattr(stats, field_name, 0) or 0)

    @classmethod
    def should_award_badge(cls, *, user, stats: UserStats, badge: Badge) -> bool:
        progress = cls.get_progress_value(user=user, stats=stats, badge=badge)
        return progress >= int(badge.requirement_value or 0)

    @classmethod
    def serialize_badge_progress(cls, *, user, stats: UserStats, badge: Badge, earned_badge_ids: set) -> dict:
        progress = cls.get_progress_value(user=user, stats=stats, badge=badge)
        requirement_value = int(badge.requirement_value or 0)
        progress_percentage = 100 if requirement_value <= 0 else min(
            100,
            (progress / requirement_value) * 100,
        )
        return {
            "id": badge.id,
            "name": badge.name,
            "slug": badge.slug,
            "description": badge.description,
            "icon": badge.icon,
            "category": badge.category,
            "points_required": badge.points_required,
            "requirement_type": badge.requirement_type,
            "requirement_value": requirement_value,
            "is_earned": badge.id in earned_badge_ids,
            "progress": progress,
            "progress_percentage": progress_percentage,
        }

    @classmethod
    def get_user_rank(cls, *, user, period: str = "all_time", stats: UserStats | None = None) -> int | None:
        normalized_period = cls.normalize_period(period)
        entry = Leaderboard.objects.filter(user=user, period=normalized_period).first()
        if entry:
            return entry.rank

        if stats is None:
            stats = UserStats.objects.filter(user=user).first()
        if not stats:
            return None

        higher_rank_count = UserStats.objects.filter(
            total_points__gt=stats.total_points
        ).count()
        return higher_rank_count + 1

    @classmethod
    def get_user_stats_payload(cls, user) -> dict:
        stats = cls.get_or_create_stats(user)
        user_badges = list(
            UserBadge.objects.filter(user=user).select_related("badge")
        )
        recent_points = user.points_history.all()[:20]
        achievements = Achievement.objects.filter(user=user)[:10]
        all_badges = Badge.objects.filter(is_active=True)
        earned_badge_ids = {item.badge_id for item in user_badges}

        return {
            "total_points": stats.total_points,
            "total_uploads": stats.total_uploads,
            "total_downloads": stats.total_downloads,
            "total_ratings": stats.total_ratings,
            "total_comments": stats.total_comments,
            "total_shares": stats.total_shares,
            "consecutive_login_days": stats.consecutive_login_days,
            "resources_shared": stats.resources_shared,
            "resources_saved": stats.resources_saved,
            "leaderboard_rank": cls.get_user_rank(user=user, period="all_time", stats=stats),
            "earned_badges": [
                {
                    "id": item.badge.id,
                    "name": item.badge.name,
                    "slug": item.badge.slug,
                    "description": item.badge.description,
                    "icon": item.badge.icon,
                    "category": item.badge.category,
                    "earned_at": item.earned_at.isoformat() if item.earned_at else None,
                }
                for item in user_badges
            ],
            "recent_points": [
                {
                    "id": point.id,
                    "action": point.action,
                    "points": point.points,
                    "description": point.description,
                    "created_at": point.created_at.isoformat(),
                }
                for point in recent_points
            ],
            "recent_achievements": [
                {
                    "id": achievement.id,
                    "title": achievement.title,
                    "description": achievement.description,
                    "points_earned": achievement.points_earned,
                    "milestone_type": achievement.milestone_type,
                    "created_at": achievement.created_at.isoformat(),
                }
                for achievement in achievements
            ],
            "all_badges": [
                cls.serialize_badge_progress(
                    user=user,
                    stats=stats,
                    badge=badge,
                    earned_badge_ids=earned_badge_ids,
                )
                for badge in all_badges
            ],
        }

    @classmethod
    def get_leaderboard_payload(cls, *, user, period: str | None = None, limit: int = 50) -> dict:
        normalized_period = cls.normalize_period(period)
        entries = Leaderboard.objects.filter(
            period=normalized_period
        ).select_related("user").order_by("rank")[:limit]

        return {
            "period": normalized_period,
            "user_rank": cls.get_user_rank(user=user, period=normalized_period),
            "entries": [
                {
                    "rank": entry.rank,
                    "user": {
                        "id": str(entry.user.id),
                        "first_name": entry.user.first_name,
                        "last_name": entry.user.last_name,
                        "email": entry.user.email,
                        "profile_image_url": getattr(entry.user, 'profile_image_url', None),
                    },
                    "total_points": entry.points,
                    "total_uploads": getattr(entry, 'total_uploads', 0) or 0,
                    "total_downloads": getattr(entry, 'total_downloads', 0) or 0,
                    "total_shares": getattr(entry, 'total_shares', 0) or 0,
                }
                for entry in entries
            ],
        }

    @classmethod
    def _period_start(cls, period: str, *, now=None):
        reference = now or timezone.now()
        if period == "daily":
            local_now = timezone.localtime(reference)
            return local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            return reference - timedelta(days=7)
        if period == "monthly":
            return reference - timedelta(days=30)
        return None

    @classmethod
    def refresh_leaderboards(cls, periods=None, *, now=None):
        """Rebuild leaderboard snapshots from point history."""
        normalized_periods = periods or ["daily", "weekly", "monthly", "all_time"]
        for period in normalized_periods:
            normalized_period = cls.normalize_period(period)
            from .models import UserPoints

            points_queryset = UserPoints.objects.all()
            start = cls._period_start(normalized_period, now=now)
            if start is not None:
                points_queryset = points_queryset.filter(created_at__gte=start)

            ranking_rows = list(
                points_queryset.values("user")
                .annotate(points=Coalesce(Sum("points"), 0))
                .filter(points__gt=0)
                .order_by("-points", "user")
            )

            Leaderboard.objects.filter(period=normalized_period).delete()
            if not ranking_rows:
                continue

            Leaderboard.objects.bulk_create(
                [
                    Leaderboard(
                        period=normalized_period,
                        user_id=row["user"],
                        rank=index,
                        points=int(row["points"] or 0),
                    )
                    for index, row in enumerate(ranking_rows, start=1)
                ]
            )

    @classmethod
    def _record_points(cls, *, stats: UserStats, action: str, description: str = "", points: int | None = None):
        resolved_points = cls.POINT_VALUES.get(action, 0) if points is None else int(points)
        if resolved_points <= 0:
            return
        stats.add_points(
            action=action,
            points=resolved_points,
            description=description,
        )

    @classmethod
    def _create_achievement_once(
        cls,
        *,
        user,
        milestone_type: str,
        title: str,
        description: str,
        points_earned: int = 0,
    ):
        Achievement.objects.get_or_create(
            user=user,
            milestone_type=milestone_type,
            defaults={
                "title": title,
                "description": description,
                "points_earned": points_earned,
            },
        )

    @classmethod
    @transaction.atomic
    def record_upload(cls, user, *, resource=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        stats.total_uploads += 1
        stats.save(update_fields=["total_uploads"])
        cls._record_points(
            stats=stats,
            action="upload_resource",
            description=(
                f"Uploaded resource: {resource.title}"
                if resource is not None
                else "Uploaded a resource"
            ),
        )
        if stats.total_uploads == 1:
            cls._create_achievement_once(
                user=user,
                milestone_type="first_upload",
                title="First Upload",
                description="Uploaded your first resource to CampusHub.",
                points_earned=cls.POINT_VALUES["upload_resource"],
            )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def record_download(cls, user, *, resource=None, personal_file=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        stats.total_downloads += 1
        stats.save(update_fields=["total_downloads"])
        target_title = getattr(resource, "title", "") or getattr(personal_file, "title", "") or "resource"
        cls._record_points(
            stats=stats,
            action="download_resource",
            description=f"Downloaded: {target_title}",
        )
        if stats.total_downloads == 1:
            cls._create_achievement_once(
                user=user,
                milestone_type="first_download",
                title="First Download",
                description="Downloaded your first file on CampusHub.",
                points_earned=cls.POINT_VALUES["download_resource"],
            )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def record_comment(cls, user, *, comment=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        stats.total_comments += 1
        stats.save(update_fields=["total_comments"])
        description = "Commented on a resource"
        if comment is not None and getattr(comment, "resource", None) is not None:
            description = f"Commented on: {comment.resource.title}"
        cls._record_points(
            stats=stats,
            action="comment_resource",
            description=description,
        )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def record_rating(cls, user, *, rating=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        stats.total_ratings += 1
        stats.save(update_fields=["total_ratings"])
        description = "Rated a resource"
        if rating is not None and getattr(rating, "resource", None) is not None:
            description = f"Rated: {rating.resource.title}"
        cls._record_points(
            stats=stats,
            action="rate_resource",
            description=description,
        )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def record_share(cls, user, *, resource=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        stats.total_shares += 1
        stats.resources_shared += 1
        stats.save(update_fields=["total_shares", "resources_shared"])
        cls._record_points(
            stats=stats,
            action="share_resource",
            description=(
                f"Shared resource: {resource.title}"
                if resource is not None
                else "Shared a resource"
            ),
        )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    def sync_saved_resources_count(cls, user) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        from apps.bookmarks.models import Bookmark

        count = Bookmark.objects.filter(user=user).count()
        if stats.resources_saved != count:
            stats.resources_saved = count
            stats.save(update_fields=["resources_saved"])
        return stats

    @classmethod
    @transaction.atomic
    def record_login(cls, user, *, now=None) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        today = timezone.localdate(now or timezone.now())
        if stats.last_login_date == today:
            return stats

        if stats.last_login_date == (today - timedelta(days=1)):
            stats.consecutive_login_days += 1
        else:
            stats.consecutive_login_days = 1
        stats.last_login_date = today
        stats.save(update_fields=["consecutive_login_days", "last_login_date"])

        cls._record_points(
            stats=stats,
            action="daily_login",
            description=f"Logged in on {today.isoformat()}",
        )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def record_email_verification(cls, user) -> UserStats | None:
        if not cls._should_track_user(user):
            return None
        stats = cls.get_or_create_stats(user)
        from .models import UserPoints

        if UserPoints.objects.filter(user=user, action="verify_email").exists():
            return stats

        cls._record_points(
            stats=stats,
            action="verify_email",
            description="Verified email address",
        )
        cls._create_achievement_once(
            user=user,
            milestone_type="email_verified",
            title="Verified Account",
            description="Verified your CampusHub email address.",
            points_earned=cls.POINT_VALUES["verify_email"],
        )
        cls.award_available_badges(user)
        cls.refresh_leaderboards()
        stats.refresh_from_db()
        return stats

    @classmethod
    @transaction.atomic
    def award_available_badges(cls, user) -> dict:
        stats = cls.get_or_create_stats(user)
        earned_badge_ids = set(
            UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
        )
        unearned_badges = Badge.objects.filter(is_active=True).exclude(id__in=earned_badge_ids)

        newly_earned = []
        for badge in unearned_badges:
            if not cls.should_award_badge(user=user, stats=stats, badge=badge):
                continue

            user_badge, created = UserBadge.objects.get_or_create(user=user, badge=badge)
            if not created:
                continue

            stats.add_points(
                action="earn_badge",
                points=badge.points_required,
                description=f"Earned badge: {badge.name}",
            )
            newly_earned.append(
                {
                    "id": badge.id,
                    "name": badge.name,
                    "slug": badge.slug,
                    "description": badge.description,
                    "icon": badge.icon,
                    "category": badge.category,
                    "points_earned": badge.points_required,
                    "earned_at": user_badge.earned_at.isoformat() if user_badge.earned_at else None,
                }
            )

        stats.refresh_from_db()
        if newly_earned:
            cls.refresh_leaderboards()
        return {
            "newly_earned": newly_earned,
            "total_badges_earned": len(newly_earned),
            "total_points": stats.total_points,
        }
