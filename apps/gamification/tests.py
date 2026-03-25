"""
Tests for gamification app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.gamification.models import (
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
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestPointCategoryModel:
    """Tests for PointCategory model."""

    def test_point_category_creation(self):
        """Test point category creation."""
        category = PointCategory.objects.create(
            name="learning",
            description="Learning activities",
        )
        assert category.id is not None
        assert category.name == "learning"

    def test_point_category_str(self):
        """Test point category string representation."""
        category = PointCategory.objects.create(name="learning")
        assert str(category) == "Learning"


@pytest.mark.django_db
class TestPointActionModel:
    """Tests for PointAction model."""

    def test_point_action_creation(self):
        """Test point action creation."""
        category = PointCategory.objects.create(name="learning")
        action = PointAction.objects.create(
            name="Upload Resource",
            category=category,
            points=10,
        )
        assert action.id is not None
        assert action.points == 10

    def test_point_action_str(self):
        """Test point action string representation."""
        category = PointCategory.objects.create(name="learning")
        action = PointAction.objects.create(
            name="Upload Resource",
            category=category,
            points=10,
        )
        assert "Upload Resource" in str(action)


@pytest.mark.django_db
class TestUserPointsModel:
    """Tests for UserPoints model."""

    def test_user_points_creation(self, user):
        """Test user points creation."""
        points = UserPoints.objects.create(
            user=user,
            action="upload_resource",
            points=10,
            total_points=100,
            level=2,
        )
        assert points.id is not None
        assert points.total_points == 100

    def test_user_points_str(self, user):
        """Test user points string representation."""
        points = UserPoints.objects.create(
            user=user,
            action="__summary__",
            total_points=100,
            level=2,
        )
        assert str(points) != ""


@pytest.mark.django_db
class TestUserStatsModel:
    """Tests for UserStats model."""

    def test_user_stats_creation(self, user):
        """Test user stats creation."""
        stats = UserStats.objects.create(
            user=user,
            total_points=100,
            total_uploads=10,
        )
        assert stats.id is not None
        assert stats.total_points == 100

    def test_user_stats_str(self, user):
        """Test user stats string representation."""
        stats = UserStats.objects.create(user=user, total_points=100)
        assert str(stats) != ""


@pytest.mark.django_db
class TestBadgeModel:
    """Tests for Badge model."""

    def test_badge_creation(self):
        """Test badge creation."""
        badge = Badge.objects.create(
            name="First Upload",
            slug="first-upload",
            points_required=10,
        )
        assert badge.id is not None
        assert badge.name == "First Upload"

    def test_badge_str(self):
        """Test badge string representation."""
        badge = Badge.objects.create(
            name="First Upload",
            slug="first-upload",
        )
        assert str(badge) == "First Upload"


@pytest.mark.django_db
class TestUserBadgeModel:
    """Tests for UserBadge model."""

    def test_user_badge_creation(self, user):
        """Test user badge creation."""
        badge = Badge.objects.create(
            name="First Upload",
            slug="first-upload",
        )
        user_badge = UserBadge.objects.create(
            user=user,
            badge=badge,
        )
        assert user_badge.id is not None
        assert user_badge.user == user


@pytest.mark.django_db
class TestLeaderboardModel:
    """Tests for Leaderboard model."""

    def test_leaderboard_creation(self, user):
        """Test leaderboard creation."""
        leaderboard = Leaderboard.objects.create(
            leaderboard_type="global",
            period="weekly",
            user=user,
            rank=1,
            points=1000,
        )
        assert leaderboard.id is not None
        assert leaderboard.rank == 1


@pytest.mark.django_db
class TestUserStreakModel:
    """Tests for UserStreak model."""

    def test_user_streak_creation(self, user):
        """Test user streak creation."""
        streak = UserStreak.objects.create(
            user=user,
            current_streak=5,
            longest_streak=10,
        )
        assert streak.id is not None
        assert streak.current_streak == 5

    def test_user_streak_str(self, user):
        """Test user streak string representation."""
        streak = UserStreak.objects.create(user=user, current_streak=5)
        assert "5 day streak" in str(streak)