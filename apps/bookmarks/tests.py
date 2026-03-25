"""
Tests for bookmarks app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookmarks.models import Bookmark

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
    )


@pytest.mark.django_db
class TestBookmarkModel:
    """Tests for Bookmark model."""

    def test_bookmark_creation(self, user, db):
        """Test bookmark model creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        bookmark = Bookmark.objects.create(
            user=user,
            resource=resource,
        )
        assert bookmark.id is not None
        assert bookmark.user == user
        assert bookmark.resource == resource

    def test_bookmark_str(self, user, db):
        """Test bookmark string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        bookmark = Bookmark.objects.create(
            user=user,
            resource=resource,
        )
        assert str(bookmark) == f"{user.email} - {resource.title}"


@pytest.mark.django_db
class TestBookmarkListAPI:
    """Tests for bookmark list endpoint."""

    def test_list_bookmarks_authenticated(self, api_client, user, db):
        """Test authenticated user can list bookmarks."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        Bookmark.objects.create(user=user, resource=resource)
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_bookmarks_unauthenticated(self, api_client):
        """Test unauthenticated user cannot list bookmarks."""
        url = reverse("bookmark-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBookmarkCreateAPI:
    """Tests for bookmark creation endpoint."""

    def test_create_bookmark(self, api_client, user, db):
        """Test user can create a bookmark."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-list")
        data = {"resource": resource.id}
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Bookmark.objects.filter(user=user, resource=resource).exists()


@pytest.mark.django_db
class TestBookmarkDeleteAPI:
    """Tests for bookmark deletion endpoint."""

    def test_delete_bookmark(self, api_client, user, db):
        """Test user can delete their bookmark."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        bookmark = Bookmark.objects.create(user=user, resource=resource)
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-detail", kwargs={"pk": bookmark.id})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Bookmark.objects.filter(id=bookmark.id).exists()


@pytest.mark.django_db
class TestBookmarkToggleAPI:
    """Tests for bookmark toggle endpoint."""

    def test_toggle_bookmark_on(self, api_client, user, db):
        """Test toggling bookmark on."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-toggle")
        data = {"resource_id": resource.id}
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert Bookmark.objects.filter(user=user, resource=resource).exists()

    def test_toggle_bookmark_off(self, api_client, user, db):
        """Test toggling bookmark off."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        Bookmark.objects.create(user=user, resource=resource)
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-toggle")
        data = {"resource_id": resource.id}
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert not Bookmark.objects.filter(user=user, resource=resource).exists()


@pytest.mark.django_db
class TestBookmarkCountAPI:
    """Tests for bookmark count endpoint."""

    def test_get_bookmark_count(self, api_client, user, db):
        """Test getting bookmark count."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        Bookmark.objects.create(user=user, resource=resource)
        
        api_client.force_authenticate(user=user)
        url = reverse("bookmark-count")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
