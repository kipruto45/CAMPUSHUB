"""
Gamification URL configuration.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"categories", views.PointCategoryViewSet, basename="point-category")
router.register(r"actions", views.PointActionViewSet, basename="point-action")
router.register(r"badges", views.BadgeViewSet, basename="badge")

urlpatterns = [
    # Stats (mobile-friendly)
    path("stats/", views.get_gamification_stats, name="gamification-stats"),
    path("check-badges/", views.check_badges, name="check-badges"),

    # Points endpoints
    path("points/", views.get_user_points, name="user-points"),
    path("points/history/", views.get_user_points_history, name="points-history"),
    path("categories/", views.get_point_categories, name="point-categories"),
    path("actions/", views.get_point_actions, name="point-actions"),
    
    # Badges endpoints
    path("badges/", views.get_user_badges, name="user-badges"),
    path("badges/all/", views.get_all_badges, name="all-badges"),
    path("badges/progress/", views.get_badge_progress, name="badge-progress"),
    
    # Leaderboard endpoints
    path("leaderboard/", views.get_leaderboard, name="leaderboard"),
    path("leaderboard/rank/", views.get_user_rank, name="user-rank"),
    
    # Streak endpoints
    path("streaks/current/", views.get_current_streak, name="current-streak"),
    path("streaks/history/", views.get_streak_history, name="streak-history"),
    path("streaks/freeze/", views.activate_streak_freeze, name="streak-freeze"),
    path("streaks/unfreeze/", views.deactivate_streak_freeze, name="streak-unfreeze"),
    
    # Achievement endpoints
    path("achievements/", views.get_all_achievements, name="all-achievements"),
    path("achievements/user/", views.get_user_achievements, name="user-achievements"),
    path("achievements/stats/", views.get_achievement_stats, name="achievement-stats"),
    path("achievements/by-category/", views.get_achievements_by_category, name="achievements-by-category"),
    path("achievements/<uuid:achievement_id>/progress/", views.get_achievement_progress, name="achievement-progress"),
    path("achievements/<uuid:achievement_id>/claim/", views.claim_achievement_reward, name="claim-achievement-reward"),
    
    # Award points (internal)
    path("award/", views.award_points, name="award-points"),
    
    # Router URLs
    path("", include(router.urls)),
]
