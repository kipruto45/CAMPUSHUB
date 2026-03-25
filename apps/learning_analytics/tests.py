"""
Tests for learning_analytics app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.learning_analytics.models import (
    LearningSession,
    LearningProgress,
    StudyStreak,
    LearningInsight,
    PerformanceMetrics,
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
class TestLearningSessionModel:
    """Tests for LearningSession model."""

    def test_learning_session_creation(self, user):
        """Test learning session creation."""
        session = LearningSession.objects.create(
            user=user,
            session_type="study",
            started_at=timezone.now(),
        )
        assert session.id is not None
        assert session.session_type == "study"

    def test_learning_session_str(self, user):
        """Test learning session string representation."""
        session = LearningSession.objects.create(
            user=user,
            session_type="study",
            started_at=timezone.now(),
        )
        assert str(session) != ""

    def test_end_session(self, user):
        """Test ending a learning session."""
        session = LearningSession.objects.create(
            user=user,
            session_type="study",
            started_at=timezone.now() - timedelta(hours=1),
        )
        session.end_session()
        assert session.ended_at is not None
        assert session.duration_minutes >= 0


@pytest.mark.django_db
class TestLearningProgressModel:
    """Tests for LearningProgress model."""

    def test_learning_progress_creation(self, user):
        """Test learning progress creation."""
        progress = LearningProgress.objects.create(
            user=user,
            progress_percentage=50.0,
        )
        assert progress.id is not None
        assert progress.progress_percentage == 50.0

    def test_learning_progress_str(self, user):
        """Test learning progress string representation."""
        progress = LearningProgress.objects.create(
            user=user,
            progress_percentage=50.0,
        )
        assert "50.0% complete" in str(progress)


@pytest.mark.django_db
class TestStudyStreakModel:
    """Tests for StudyStreak model."""

    def test_study_streak_creation(self, user):
        """Test study streak creation."""
        streak = StudyStreak.objects.create(
            user=user,
            current_streak=5,
            longest_streak=10,
        )
        assert streak.id is not None
        assert streak.current_streak == 5

    def test_study_streak_str(self, user):
        """Test study streak string representation."""
        streak = StudyStreak.objects.create(user=user, current_streak=5)
        assert "5 day streak" in str(streak)


@pytest.mark.django_db
class TestLearningInsightModel:
    """Tests for LearningInsight model."""

    def test_learning_insight_creation(self, user):
        """Test learning insight creation."""
        insight = LearningInsight.objects.create(
            user=user,
            insight_type="recommendation",
            title="Study More",
            description="You should study more",
        )
        assert insight.id is not None
        assert insight.insight_type == "recommendation"

    def test_learning_insight_str(self, user):
        """Test learning insight string representation."""
        insight = LearningInsight.objects.create(
            user=user,
            insight_type="recommendation",
            title="Study More",
            description="Test",
        )
        assert "recommendation" in str(insight)


@pytest.mark.django_db
class TestPerformanceMetricsModel:
    """Tests for PerformanceMetrics model."""

    def test_performance_metrics_creation(self, user):
        """Test performance metrics creation."""
        metrics = PerformanceMetrics.objects.create(
            user=user,
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=7),
            total_study_time_minutes=300,
        )
        assert metrics.id is not None
        assert metrics.total_study_time_minutes == 300

    def test_performance_metrics_str(self, user):
        """Test performance metrics string representation."""
        metrics = PerformanceMetrics.objects.create(
            user=user,
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=7),
        )
        assert str(metrics) != ""