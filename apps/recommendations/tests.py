"""
Tests for recommendations app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.recommendations.models import UserInterestProfile, RecommendationCache

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestUserInterestProfileModel:
    """Tests for UserInterestProfile model."""

    def test_user_interest_profile_creation(self, user):
        """Test user interest profile creation."""
        profile = UserInterestProfile.objects.create(
            user=user,
            favorite_tags=["python", "django"],
        )
        assert profile.id is not None
        assert "python" in profile.favorite_tags

    def test_user_interest_profile_str(self, user):
        """Test user interest profile string representation."""
        profile = UserInterestProfile.objects.create(user=user)
        assert str(profile) == f"Interest profile for {user.email}"


@pytest.mark.django_db
class TestRecommendationCacheModel:
    """Tests for RecommendationCache model."""

    def test_recommendation_cache_creation(self, user):
        """Test recommendation cache creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        cache = RecommendationCache.objects.create(
            user=user,
            resource=resource,
            category=RecommendationCache.CATEGORY_FOR_YOU,
            score=0.95,
            rank=1,
        )
        assert cache.id is not None
        assert cache.score == 0.95

    def test_recommendation_cache_str(self, user):
        """Test recommendation cache string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        cache = RecommendationCache.objects.create(
            user=user,
            resource=resource,
            category=RecommendationCache.CATEGORY_FOR_YOU,
        )
        assert "for_you" in str(cache)