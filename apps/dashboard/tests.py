"""
Tests for the Dashboard API.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.resources.models import Resource, UserStorage


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com", password="testpass123", full_name="Test User"
    )


@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated test client."""
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        email="otheruser@example.com", password="otherpass123", full_name="Other User"
    )


@pytest.fixture
def resource(db, user):
    """Create a test resource."""
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering")
    department = faculty.departments.create(name="Computer Science")
    course = department.courses.create(name="Computer Science", code="CS")

    return Resource.objects.create(
        title="Test Resource",
        description="Test Description",
        file="test.pdf",
        file_type="pdf",
        file_size=1024,
        uploader=user,
        course=course,
        status="approved",
    )


@pytest.mark.django_db
class TestDashboardView:
    """Tests for the main Dashboard API endpoint."""

    def test_dashboard_requires_authentication(self, client):
        """Test that unauthenticated requests are rejected."""
        url = reverse("dashboard:dashboard")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_returns_data_for_authenticated_user(
        self, authenticated_client, user
    ):
        """Test that authenticated users can access their dashboard."""
        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "user_summary" in response.data
        assert "quick_stats" in response.data
        assert "recent_activity" in response.data

    def test_dashboard_user_summary_includes_profile_completion(
        self, authenticated_client, user
    ):
        """Test that user summary includes profile completion."""
        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "profile_completion" in response.data["user_summary"]
        assert "is_profile_complete" in response.data["user_summary"]

    def test_dashboard_quick_stats_includes_counts(self, authenticated_client, user):
        """Test that quick stats include all expected counts."""
        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        stats = response.data["quick_stats"]
        assert "bookmarks_count" in stats
        assert "personal_files_count" in stats
        assert "uploads_count" in stats
        assert "downloads_count" in stats
        assert "storage_used_mb" in stats
        assert "storage_limit_mb" in stats


@pytest.mark.django_db
class TestDashboardStatsView:
    """Tests for the Dashboard Stats API endpoint."""

    def test_stats_requires_authentication(self, client):
        """Test that unauthenticated requests are rejected."""
        url = reverse("dashboard:dashboard-stats")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_stats_returns_counts(self, authenticated_client, user):
        """Test that stats endpoint returns correct counts."""
        url = reverse("dashboard:dashboard-stats")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "bookmarks_count" in response.data
        assert response.data["bookmarks_count"] == 0


@pytest.mark.django_db
class TestDashboardRecentActivityView:
    """Tests for the Dashboard Recent Activity API endpoint."""

    def test_activity_requires_authentication(self, client):
        """Test that unauthenticated requests are rejected."""
        url = reverse("dashboard:dashboard-activity")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activity_returns_recent_items(self, authenticated_client, user, resource):
        """Test that activity endpoint returns recent items."""
        url = reverse("dashboard:dashboard-activity")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "recent_uploads" in response.data
        assert "recent_downloads" in response.data
        assert "recent_bookmarks" in response.data


@pytest.mark.django_db
class TestDashboardRecommendationsView:
    """Tests for the Dashboard Recommendations API endpoint."""

    def test_recommendations_requires_authentication(self, client):
        """Test that unauthenticated requests are rejected."""
        url = reverse("dashboard:dashboard-recommendations")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_recommendations_returns_resources(
        self, authenticated_client, user, resource
    ):
        """Test that recommendations endpoint returns resources."""
        url = reverse("dashboard:dashboard-recommendations")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "trending" in response.data
        assert "course_related" in response.data
        assert "recently_added" in response.data


@pytest.mark.django_db
class TestDashboardDataAggregation:
    """Tests for dashboard data aggregation from multiple sources."""

    def test_dashboard_includes_bookmarks(self, authenticated_client, user, resource):
        """Test that dashboard includes bookmark data."""
        Bookmark.objects.create(user=user, resource=resource)

        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["quick_stats"]["bookmarks_count"] == 1

    def test_dashboard_includes_uploads(self, authenticated_client, user, resource):
        """Test that dashboard includes upload data."""
        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["quick_stats"]["uploads_count"] >= 1

    def test_dashboard_includes_downloads(self, authenticated_client, user, resource):
        """Test that dashboard includes download data."""
        Download.objects.create(user=user, resource=resource)

        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["quick_stats"]["downloads_count"] == 1

    def test_dashboard_includes_storage_info(self, authenticated_client, user):
        """Test that dashboard includes storage information."""
        UserStorage.objects.create(user=user, used_storage=1024 * 1024)

        url = reverse("dashboard:dashboard")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        stats = response.data["quick_stats"]
        assert "storage_used_mb" in stats
        assert "storage_limit_mb" in stats
