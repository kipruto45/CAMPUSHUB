"""
Gamification views for API endpoints.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.accounts.models import User

from . import services
from .models import (
    PointCategory,
    PointAction,
    UserPoints,
    UserStats,
    PointTransaction,
    Badge,
    UserBadge,
    Leaderboard,
    UserStreak,
    StreakHistory,
    Achievement,
    AchievementTier,
    AchievementCategory,
    UserAchievement,
)
from .serializers import (
    PointCategorySerializer,
    PointActionSerializer,
    UserPointsSerializer,
    PointTransactionSerializer,
    BadgeSerializer,
    UserBadgeSerializer,
    LeaderboardEntrySerializer,
    AwardPointsRequestSerializer,
    UserStreakSerializer,
    StreakHistorySerializer,
    StreakStatusSerializer,
    AchievementSerializer,
    AchievementTierSerializer,
    AchievementCategorySerializer,
    UserAchievementSerializer,
    AchievementProgressSerializer,
    AchievementStatsSerializer,
    ClaimRewardResponseSerializer,
)

def _safe_count(queryset):
    try:
        return queryset.count()
    except Exception:
        return 0


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_gamification_stats(request, *args, **kwargs):
    """
    Get a mobile-friendly gamification snapshot.
    GET /api/gamification/stats/
    """
    user = request.user
    points_data = services.GamificationService.get_user_points(user)
    stats = services.GamificationService.get_or_create_user_stats(user)

    earned_badges_qs = UserBadge.objects.filter(user=user, is_active=True).select_related("badge")
    earned_badges = []
    earned_badge_ids = set()
    for user_badge in earned_badges_qs:
        badge = user_badge.badge
        earned_badge_ids.add(str(badge.id))
        earned_badges.append(
            {
                "id": str(badge.id),
                "slug": badge.slug,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "category": getattr(getattr(badge, "category", None), "name", ""),
            }
        )

    metric_map = {
        "total_uploads": stats.total_uploads,
        "total_downloads": stats.total_downloads,
        "total_shares": stats.total_shares,
        "total_comments": stats.total_comments,
        "total_ratings": stats.total_ratings,
        "resources_shared": stats.resources_shared,
        "resources_saved": stats.resources_saved,
        "consecutive_login_days": stats.consecutive_login_days,
        "email_verified": 1 if getattr(user, "is_verified", False) else 0,
    }

    all_badges = []
    for badge in Badge.objects.filter(is_active=True).order_by("name"):
        requirement_type = (badge.requirement_type or "").strip()
        requirement_value = int(badge.requirement_value or badge.points_required or 0)
        progress = 0
        if requirement_type:
            progress = int(metric_map.get(requirement_type, 0) or 0)
        elif badge.points_required:
            progress = int(stats.total_points or 0)
            requirement_type = "points"
            requirement_value = int(badge.points_required)

        is_earned = str(badge.id) in earned_badge_ids
        progress_pct = 100 if is_earned else (
            min(100, int((progress / requirement_value) * 100)) if requirement_value else 0
        )

        all_badges.append(
            {
                "id": str(badge.id),
                "slug": badge.slug,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "category": getattr(getattr(badge, "category", None), "name", ""),
                "requirement_type": requirement_type,
                "requirement_value": requirement_value,
                "is_earned": is_earned,
                "progress": progress,
                "progress_percentage": progress_pct,
            }
        )

    leaderboard_rank = (
        Leaderboard.objects.filter(user=user, period="all_time").values_list("rank", flat=True).first()
    )
    recent_points = list(
        UserPoints.objects.filter(user=user)
        .exclude(action="__summary__")
        .order_by("-created_at")
        .values("action", "points", "description", "created_at")[:10]
    )
    recent_achievements = list(
        Achievement.objects.filter(user=user)
        .order_by("-created_at")
        .values("title", "description", "points_earned", "milestone_type", "created_at")[:10]
    )

    return Response(
        {
            "total_points": int(stats.total_points or points_data.get("total_points", 0) or 0),
            "total_uploads": int(stats.total_uploads or 0),
            "total_downloads": int(stats.total_downloads or 0),
            "total_ratings": int(stats.total_ratings or 0),
            "total_comments": int(stats.total_comments or 0),
            "total_shares": int(stats.total_shares or 0),
            "consecutive_login_days": int(stats.consecutive_login_days or 0),
            "resources_saved": int(stats.resources_saved or 0),
            "leaderboard_rank": leaderboard_rank,
            "recent_points": recent_points,
            "recent_achievements": recent_achievements,
            "earned_badges": earned_badges,
            "all_badges": all_badges,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_badges(request, *args, **kwargs):
    """
    Trigger a badge eligibility check and return any newly awarded badges.
    POST /api/gamification/check-badges/
    """
    user = request.user
    awarded = services.GamificationService.check_badge_eligibility(user)
    data = []
    for badge in awarded or []:
        data.append(
            {
                "id": str(getattr(badge, "id", "")),
                "slug": getattr(badge, "slug", ""),
                "name": getattr(badge, "name", "") or "Badge",
                "description": getattr(badge, "description", "") or "",
                "icon": getattr(badge, "icon", "") or "star",
                "category": (
                    getattr(getattr(badge, "category", None), "name", None)
                    or getattr(badge, "category", "")
                    or ""
                ),
            }
        )
    return Response(
        {
            "awarded": data,
            "count": len(data),
            "newly_earned": data,
            "total_badges_earned": len(data),
        }
    )


@extend_schema_view(
    retrieve=extend_schema(operation_id="api_gamification_category_retrieve")
)
class PointCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for point categories."""

    queryset = PointCategory.objects.filter(is_active=True)
    serializer_class = PointCategorySerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    retrieve=extend_schema(operation_id="api_gamification_action_retrieve")
)
class PointActionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for point actions."""

    queryset = PointAction.objects.filter(is_active=True)
    serializer_class = PointActionSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    retrieve=extend_schema(operation_id="api_gamification_badge_retrieve")
)
class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for badges."""

    queryset = Badge.objects.filter(is_active=True)
    serializer_class = BadgeSerializer
    permission_classes = [AllowAny]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_points(request):
    """
    Get user points.
    GET /api/gamification/points/
    """
    user = request.user
    points_data = services.GamificationService.get_user_points(user)
    serializer = UserPointsSerializer(points_data)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_points_history(request):
    """
    Get user points history.
    GET /api/gamification/points/history/
    """
    user = request.user
    limit = int(request.query_params.get("limit", 50))
    history = services.GamificationService.get_user_points_history(user, limit)
    serializer = PointTransactionSerializer(history, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_badges(request):
    """
    Get user badges.
    GET /api/gamification/badges/
    """
    user = request.user
    badges = services.GamificationService.get_user_badges(user)
    serializer = UserBadgeSerializer(badges, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_badge_progress(request):
    """
    Get user progress towards badges.
    GET /api/gamification/badges/progress/
    """
    user = request.user
    progress = services.GamificationService.get_user_badge_progress(user)
    return Response(progress)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_leaderboard(request, *args, **kwargs):
    """
    Get leaderboard.
    GET /api/gamification/leaderboard/
    
    Query params:
        - type: 'global', 'faculty', or 'department' (default: 'global')
        - period: 'weekly', 'monthly', or 'all_time' (default: 'all_time')
        - faculty_id: Faculty ID for faculty leaderboard
        - department_id: Department ID for department leaderboard
        - limit: Maximum number of users (default: 100)
    """
    leaderboard_type = request.query_params.get("type", "global")
    period = request.query_params.get("period", "all_time")
    faculty_id = request.query_params.get("faculty_id")
    department_id = request.query_params.get("department_id")
    limit = int(request.query_params.get("limit", 100))
    valid_periods = {"daily", "weekly", "monthly", "all_time"}
    if period not in valid_periods:
        period = "all_time"

    entries_qs = (
        Leaderboard.objects.filter(period=period, user__isnull=False)
        .select_related("user")
        .order_by("rank", "-points")[:limit]
    )

    entries = [
        {
            "rank": entry.rank,
            "user_id": str(entry.user_id),
            "user_name": entry.user.get_full_name() or entry.user.email,
            "user_email": entry.user.email,
            "profile_image": entry.user.profile_image.url if entry.user.profile_image else None,
            "faculty": entry.user.faculty.name if entry.user.faculty else None,
            "department": entry.user.department.name if entry.user.department else None,
            "points": entry.points,
        }
        for entry in entries_qs
    ]

    # Fall back to computed leaderboard if explicit rows don't exist.
    if not entries:
        entries = services.LeaderboardService.get_leaderboard(
            leaderboard_type=leaderboard_type,
            period=period,
            faculty_id=int(faculty_id) if faculty_id else None,
            department_id=int(department_id) if department_id else None,
            limit=limit,
        )

    user_rank = None
    if request.user.is_authenticated:
        match = next((row for row in entries if str(row.get("user_id")) == str(request.user.id)), None)
        user_rank = match.get("rank") if match else None

    serializer = LeaderboardEntrySerializer(entries, many=True)
    return Response(
        {
            "leaderboard_type": leaderboard_type,
            "period": period,
            "entries": serializer.data,
            "user_rank": user_rank,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_rank(request):
    """
    Get user's rank in the leaderboard.
    GET /api/gamification/leaderboard/rank/
    """
    leaderboard_type = request.query_params.get("type", "global")
    period = request.query_params.get("period", "all_time")
    
    rank = services.LeaderboardService.get_user_rank(
        user=request.user,
        leaderboard_type=leaderboard_type,
        period=period,
    )
    
    if rank:
        return Response(rank)
    
    return Response({
        "rank": None,
        "message": "User not found in leaderboard",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def award_points(request):
    """
    Award points to a user.
    POST /api/gamification/award/
    
    Request body (one of):
        - action_name: Name of the action to award points for
        - category_name + points: Custom points award
    
    For internal use or manual awarding.
    """
    serializer = AwardPointsRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    
    # Determine if this is for the current user or another user
    target_user = request.user
    if data.get("user_id") and request.user.is_staff:
        try:
            target_user = User.objects.get(id=data["user_id"])
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
    
    # Award points based on action or custom
    if data.get("action_name"):
        success, message, points = services.GamificationService.award_points(
            user=target_user,
            action_name=data["action_name"],
            description=data.get("description", ""),
            reference_id=data.get("reference_id", ""),
            reference_type=data.get("reference_type", ""),
        )
    elif data.get("category_name") and data.get("points"):
        success, message, points = services.GamificationService.award_custom_points(
            user=target_user,
            category_name=data["category_name"],
            points=data["points"],
            description=data.get("description", ""),
            reference_id=data.get("reference_id", ""),
            reference_type=data.get("reference_type", ""),
        )
    else:
        return Response(
            {"error": "Either action_name or category_name+points required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if success:
        return Response({
            "success": True,
            "message": message,
            "points_awarded": points,
            "user_points": services.GamificationService.get_user_points(target_user),
        })
    else:
        return Response(
            {"success": False, "error": message},
            status=status.HTTP_400_BAD_REQUEST,
        )


@extend_schema(operation_id="api_gamification_categories_list")
@api_view(["GET"])
@permission_classes([AllowAny])
def get_point_categories(request):
    """Get all point categories."""
    categories = PointCategory.objects.filter(is_active=True)
    serializer = PointCategorySerializer(categories, many=True)
    return Response(serializer.data)


@extend_schema(operation_id="api_gamification_actions_list")
@api_view(["GET"])
@permission_classes([AllowAny])
def get_point_actions(request):
    """Get all point actions."""
    actions = PointAction.objects.filter(is_active=True)
    serializer = PointActionSerializer(actions, many=True)
    return Response(serializer.data)


@extend_schema(operation_id="api_gamification_badges_list")
@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_badges(request):
    """Get all available badges."""
    badges = services.GamificationService.get_all_badges()
    serializer = BadgeSerializer(badges, many=True)
    return Response(serializer.data)


# ============== Streak Views ==============


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_streak(request):
    """
    Get current user's streak status.
    GET /api/gamification/streaks/current/
    """
    user = request.user
    streak_status = services.StreakService.get_streak_status(user)
    serializer = StreakStatusSerializer(streak_status)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_streak_history(request):
    """
    Get user's streak history.
    GET /api/gamification/streaks/history/
    """
    user = request.user
    limit = int(request.query_params.get("limit", 30))
    history = services.StreakService.get_streak_history(user, limit)
    serializer = StreakHistorySerializer(history, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def activate_streak_freeze(request):
    """
    Activate streak freeze to pause streak for a day.
    POST /api/gamification/streaks/freeze/
    """
    user = request.user
    success, message = services.StreakService.activate_streak_freeze(user)
    
    if success:
        return Response({
            "success": True,
            "message": message,
        })
    else:
        return Response(
            {"success": False, "error": message},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deactivate_streak_freeze(request):
    """
    Deactivate streak freeze.
    POST /api/gamification/streaks/unfreeze/
    """
    user = request.user
    success, message = services.StreakService.deactivate_streak_freeze(user)
    
    if success:
        return Response({
            "success": True,
            "message": message,
        })
    else:
        return Response(
            {"success": False, "error": message},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ============== Achievement Views ==============


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_achievements(request):
    """
    Get all achievements.
    GET /api/gamification/achievements/
    
    Query params:
        - category: Filter by category (learning, social, engagement, special)
        - tier: Filter by tier (bronze, silver, gold, diamond)
        - featured: Filter by featured (true/false)
    """
    category = request.query_params.get("category")
    tier = request.query_params.get("tier")
    featured = request.query_params.get("featured")
    
    if featured is not None:
        featured = featured.lower() == "true"
    
    achievements = services.AchievementService.get_all_achievements(
        category=category,
        tier=tier,
        is_featured=featured,
    )
    serializer = AchievementSerializer(achievements, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_achievements(request):
    """
    Get user's achievements with progress.
    GET /api/gamification/achievements/user/
    
    Query params:
        - include_completed: Include completed achievements (default: true)
        - include_in_progress: Include in-progress achievements (default: true)
    """
    user = request.user
    include_completed = request.query_params.get("include_completed", "true").lower() == "true"
    include_in_progress = request.query_params.get("include_in_progress", "true").lower() == "true"
    
    user_achievements = services.AchievementService.get_user_achievements(
        user=user,
        include_completed=include_completed,
        include_in_progress=include_in_progress,
    )
    serializer = UserAchievementSerializer(user_achievements, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_achievement_progress(request, achievement_id):
    """
    Get user's progress for a specific achievement.
    GET /api/gamification/achievements/{id}/progress/
    """
    user = request.user
    progress = services.AchievementService.get_achievement_progress(user, achievement_id)
    
    if progress is None:
        return Response(
            {"error": "Achievement not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    serializer = AchievementProgressSerializer(progress)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def claim_achievement_reward(request, achievement_id):
    """
    Claim reward for a completed achievement.
    POST /api/gamification/achievements/{id}/claim/
    """
    user = request.user
    success, message, rewards = services.AchievementService.claim_achievement_reward(
        user=user,
        achievement_id=achievement_id,
    )
    
    if success:
        return Response({
            "success": True,
            "message": message,
            "rewards": rewards,
        })
    else:
        return Response(
            {"success": False, "error": message},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_achievement_stats(request):
    """
    Get user's achievement statistics.
    GET /api/gamification/achievements/stats/
    """
    user = request.user
    stats = services.AchievementService.get_user_achievement_stats(user)
    serializer = AchievementStatsSerializer(stats)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_achievements_by_category(request):
    """
    Get achievements grouped by category.
    GET /api/gamification/achievements/by-category/
    
    Optional: Include user progress if authenticated.
    """
    user = request.user if request.user.is_authenticated else None
    achievements_by_category = services.AchievementService.get_achievements_by_category(user)
    return Response(achievements_by_category)
