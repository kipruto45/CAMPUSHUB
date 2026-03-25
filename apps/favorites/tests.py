"""
Tests for favorites app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.favorites.models import Favorite, FavoriteType

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestFavoriteModel:
    """Tests for Favorite model."""

    def test_favorite_creation(self, user):
        """Test favorite creation for resource."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        assert favorite.id is not None
        assert favorite.favorite_type == "resource"
        assert favorite.resource == resource

    def test_favorite_str(self, user):
        """Test favorite string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        assert user.email in str(favorite)

    def test_target_title_property(self, user):
        """Test target_title property."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        assert favorite.target_title == "Test Resource"

    def test_target_property(self, user):
        """Test target property returns resource."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        assert favorite.target == resource