"""Tests for gamification endpoints and service behavior."""

import pytest

from apps.gamification.models import (
    Achievement,
    Badge,
    Leaderboard,
    UserBadge,
    UserPoints,
    UserStats,
)


@pytest.fixture
def upload_badge(db):
    return Badge.objects.create(
        name="Uploader",
        slug="uploader",
        description="Upload one resource",
        icon="fa-upload",
        category="uploads",
        points_required=10,
        requirement_type="total_uploads",
        requirement_value=1,
    )


@pytest.fixture
def download_badge(db):
    return Badge.objects.create(
        name="Downloader",
        slug="downloader",
        description="Download five resources",
        icon="fa-download",
        category="downloads",
        points_required=15,
        requirement_type="total_downloads",
        requirement_value=5,
    )


@pytest.mark.django_db
def test_gamification_stats_endpoint_returns_progress_and_rank(
    authenticated_client,
    user,
    upload_badge,
    download_badge,
):
    stats, _ = UserStats.objects.get_or_create(user=user)
    stats.total_points = 25
    stats.total_uploads = 1
    stats.total_downloads = 3
    stats.total_shares = 2
    stats.save()
    UserBadge.objects.create(user=user, badge=upload_badge)
    UserPoints.objects.create(
        user=user,
        action="upload_resource",
        points=10,
        description="Uploaded notes",
    )
    Achievement.objects.create(
        user=user,
        title="First Contribution",
        description="Uploaded a helpful resource",
        points_earned=10,
        milestone_type="first_upload",
    )
    Leaderboard.objects.create(period="all_time", user=user, rank=4, points=25)

    response = authenticated_client.get("/api/gamification/stats/")

    assert response.status_code == 200
    assert response.data["total_points"] == 25
    assert response.data["leaderboard_rank"] == 4
    assert len(response.data["earned_badges"]) == 1
    assert response.data["earned_badges"][0]["slug"] == "uploader"
    all_badges = {badge["slug"]: badge for badge in response.data["all_badges"]}
    assert all_badges["uploader"]["is_earned"] is True
    assert all_badges["uploader"]["progress"] == 1
    assert all_badges["downloader"]["progress"] == 3
    assert all_badges["downloader"]["progress_percentage"] == 60
    assert response.data["recent_points"][0]["action"] == "upload_resource"
    assert response.data["recent_achievements"][0]["milestone_type"] == "first_upload"


@pytest.mark.django_db
def test_leaderboard_defaults_invalid_period_and_returns_entries(
    authenticated_client,
    user,
    admin_user,
):
    user_stats, _ = UserStats.objects.get_or_create(user=user)
    user_stats.total_points = 50
    user_stats.save(update_fields=["total_points"])
    admin_stats, _ = UserStats.objects.get_or_create(user=admin_user)
    admin_stats.total_points = 90
    admin_stats.save(update_fields=["total_points"])
    Leaderboard.objects.create(period="all_time", user=admin_user, rank=1, points=90)
    Leaderboard.objects.create(period="all_time", user=user, rank=2, points=50)

    response = authenticated_client.get("/api/gamification/leaderboard/?period=invalid")

    assert response.status_code == 200
    assert response.data["period"] == "all_time"
    assert response.data["user_rank"] == 2
    assert response.data["entries"][0]["user_email"] == admin_user.email
    assert response.data["entries"][1]["user_email"] == user.email


@pytest.mark.django_db
def test_check_badges_accepts_post_and_awards_points_once(
    authenticated_client,
    user,
    upload_badge,
):
    stats, _ = UserStats.objects.get_or_create(user=user)
    stats.total_uploads = 1
    stats.total_points = 0
    stats.save()

    first_response = authenticated_client.post("/api/gamification/check-badges/", {}, format="json")
    second_response = authenticated_client.post("/api/gamification/check-badges/", {}, format="json")

    assert first_response.status_code == 200
    assert first_response.data["total_badges_earned"] == 1
    assert first_response.data["newly_earned"][0]["slug"] == "uploader"
    assert second_response.status_code == 200
    assert second_response.data["total_badges_earned"] == 0

    stats.refresh_from_db()
    assert stats.total_points == 10
    assert UserBadge.objects.filter(user=user, badge=upload_badge).count() == 1
    assert UserPoints.objects.filter(user=user, action="earn_badge").count() == 1


@pytest.mark.django_db
def test_gamification_model_strings_use_custom_user_labels(user, upload_badge):
    stats, _ = UserStats.objects.get_or_create(user=user)
    stats.total_points = 7
    stats.save(update_fields=["total_points"])
    user_badge = UserBadge.objects.create(user=user, badge=upload_badge)
    points = UserPoints.objects.create(user=user, action="upload_resource", points=3)
    achievement = Achievement.objects.create(
        user=user,
        title="Milestone",
        description="Reached a milestone",
        milestone_type="test_milestone",
    )
    leaderboard = Leaderboard.objects.create(period="daily", user=user, rank=1, points=7)

    assert user.get_full_name() in str(stats)
    assert upload_badge.name in str(user_badge)
    assert "upload_resource" in str(points)
    assert "Milestone" in str(achievement)
    assert user.get_full_name() in str(leaderboard)
