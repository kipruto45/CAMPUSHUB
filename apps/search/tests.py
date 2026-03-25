"""
Tests for search app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.search.models import SearchIndex, RecentSearch

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestSearchIndexModel:
    """Tests for SearchIndex model."""

    def test_search_index_creation(self, user):
        """Test search index creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        index = SearchIndex.objects.create(
            resource=resource,
            search_document="Test Resource content",
        )
        assert index.id is not None
        assert index.is_active is True


@pytest.mark.django_db
class TestRecentSearchModel:
    """Tests for RecentSearch model."""

    def test_recent_search_creation(self, user):
        """Test recent search creation."""
        search = RecentSearch.objects.create(
            user=user,
            query="python tutorial",
            results_count=10,
        )
        assert search.id is not None
        assert search.query == "python tutorial"

    def test_recent_search_str(self, user):
        """Test recent search string representation."""
        search = RecentSearch.objects.create(
            user=user,
            query="python",
        )
        assert "python" in str(search)