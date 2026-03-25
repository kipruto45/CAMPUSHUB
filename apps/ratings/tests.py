"""
Tests for ratings app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.ratings.models import Rating

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def user2(db):
    """Create another test user."""
    return User.objects.create_user(
        email="test2@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestRatingModel:
    """Tests for Rating model."""

    def test_rating_creation(self, user, user2):
        """Test rating creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        rating = Rating.objects.create(
            user=user2,
            resource=resource,
            value=5,
        )
        assert rating.id is not None
        assert rating.value == 5

    def test_rating_str(self, user, user2):
        """Test rating string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        rating = Rating.objects.create(
            user=user2,
            resource=resource,
            value=4,
        )
        assert "4" in str(rating)

    def test_rating_value_min_validation(self, user, user2):
        """Test rating value minimum validation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        rating = Rating(
            user=user2,
            resource=resource,
            value=0,
        )
        with pytest.raises(ValidationError):
            rating.full_clean()

    def test_rating_value_max_validation(self, user, user2):
        """Test rating value maximum validation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        rating = Rating(
            user=user2,
            resource=resource,
            value=6,
        )
        with pytest.raises(ValidationError):
            rating.full_clean()