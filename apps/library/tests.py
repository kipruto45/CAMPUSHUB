"""
Tests for library app - services and views.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestLibraryServices:
    """Tests for Library services."""

    def test_library_service_import(self):
        """Test LibraryService can be imported."""
        from apps.library.services import LibraryService
        assert LibraryService is not None

    def test_library_permissions_import(self):
        """Test library permissions can be imported."""
        from apps.library.permissions import LibraryPermission
        assert LibraryPermission is not None


@pytest.mark.django_db
class TestLibraryViews:
    """Tests for Library views."""

    def test_library_urls_exist(self):
        """Test library URLs can be imported."""
        from apps.library import urls
        assert urls is not None

    def test_library_views_import(self):
        """Test library views can be imported."""
        from apps.library import views
        assert views is not None