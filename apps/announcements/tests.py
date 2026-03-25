"""
Tests for announcements app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementStatus, AnnouncementType

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    user = User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
    )
    return user


@pytest.fixture
def regular_user(db):
    """Create a regular user."""
    user = User.objects.create_user(
        email="user@example.com",
        password="userpass123",
    )
    return user


@pytest.fixture
def announcement(db, admin_user):
    """Create a test announcement."""
    return Announcement.objects.create(
        title="Test Announcement",
        content="This is a test announcement content.",
        status=AnnouncementStatus.PUBLISHED,
        announcement_type=AnnouncementType.GENERAL,
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestAnnouncementModel:
    """Tests for Announcement model."""

    def test_announcement_creation(self, announcement):
        """Test announcement is created correctly."""
        assert announcement.id is not None
        assert announcement.title == "Test Announcement"
        assert announcement.status == AnnouncementStatus.PUBLISHED

    def test_announcement_str(self, announcement):
        """Test announcement string representation."""
        assert str(announcement) == "Test Announcement"

    def test_announcement_slug_generation(self, announcement):
        """Test announcement slug is auto-generated."""
        assert announcement.slug == "test-announcement"

    def test_announcement_is_pinned_default(self, announcement):
        """Test announcement is not pinned by default."""
        assert announcement.is_pinned is False


@pytest.mark.django_db
class TestAnnouncementListAPI:
    """Tests for announcement list endpoint."""

    def test_list_announcements_for_admin(self, api_client, admin_user, announcement):
        """Test admin can see all announcements."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcement-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_list_announcements_for_regular_user(
        self, api_client, regular_user, announcement
    ):
        """Test regular user can see published announcements."""
        api_client.force_authenticate(user=regular_user)
        url = reverse("announcement-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_announcements_unauthenticated(self, api_client, announcement):
        """Test unauthenticated user can see announcements."""
        url = reverse("announcement-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAnnouncementDetailAPI:
    """Tests for announcement detail endpoint."""

    def test_retrieve_announcement(self, api_client, admin_user, announcement):
        """Test retrieving a single announcement."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcement-detail", kwargs={"slug": announcement.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == announcement.title

    def test_retrieve_nonexistent_announcement(self, api_client, admin_user):
        """Test retrieving nonexistent announcement returns 404."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcement-detail", kwargs={"slug": "nonexistent"})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAnnouncementCreateAPI:
    """Tests for announcement creation endpoint."""

    def test_create_announcement_as_admin(
        self, api_client, admin_user
    ):
        """Test admin can create announcement."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcementadmin-list")
        data = {
            "title": "New Announcement",
            "content": "New announcement content",
            "status": AnnouncementStatus.DRAFT,
            "announcement_type": AnnouncementType.GENERAL,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Announcement"

    def test_create_announcement_as_regular_user(
        self, api_client, regular_user
    ):
        """Test regular user cannot create announcement."""
        api_client.force_authenticate(user=regular_user)
        url = reverse("announcementadmin-list")
        data = {
            "title": "New Announcement",
            "content": "New announcement content",
            "status": AnnouncementStatus.DRAFT,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAnnouncementUpdateAPI:
    """Tests for announcement update endpoint."""

    def test_update_announcement_as_admin(
        self, api_client, admin_user, announcement
    ):
        """Test admin can update announcement."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcementadmin-detail", kwargs={"slug": announcement.slug})
        data = {"title": "Updated Title"}
        response = api_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Title"

    def test_update_announcement_as_regular_user(
        self, api_client, regular_user, announcement
    ):
        """Test regular user cannot update announcement."""
        api_client.force_authenticate(user=regular_user)
        url = reverse("announcementadmin-detail", kwargs={"slug": announcement.slug})
        data = {"title": "Updated Title"}
        response = api_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAnnouncementPublishAPI:
    """Tests for announcement publish endpoint."""

    def test_publish_announcement(self, api_client, admin_user, announcement):
        """Test admin can publish announcement."""
        api_client.force_authenticate(user=admin_user)
        announcement.status = AnnouncementStatus.DRAFT
        announcement.save()
        url = reverse("announcementadmin-publish", kwargs={"slug": announcement.slug})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        announcement.refresh_from_db()
        assert announcement.status == AnnouncementStatus.PUBLISHED


@pytest.mark.django_db
class TestAnnouncementArchiveAPI:
    """Tests for announcement archive endpoint."""

    def test_archive_announcement(self, api_client, admin_user, announcement):
        """Test admin can archive announcement."""
        api_client.force_authenticate(user=admin_user)
        url = reverse("announcementadmin-archive", kwargs={"slug": announcement.slug})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        announcement.refresh_from_db()
        assert announcement.status == AnnouncementStatus.ARCHIVED


@pytest.mark.django_db
class TestPinnedAnnouncements:
    """Tests for pinned announcements endpoint."""

    def test_get_pinned_announcements(self, api_client, admin_user, announcement):
        """Test getting pinned announcements."""
        api_client.force_authenticate(user=admin_user)
        announcement.is_pinned = True
        announcement.save()
        url = reverse("announcement-pinned")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
