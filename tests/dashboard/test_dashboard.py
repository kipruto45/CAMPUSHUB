"""Tests for dashboard module endpoints."""

import pytest
from rest_framework import status

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.resources.models import Resource


@pytest.fixture
def dashboard_resource(db, user):
    """Create a resource uploaded by the authenticated user."""
    return Resource.objects.create(
        title="My Upload",
        resource_type="notes",
        uploaded_by=user,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def public_resource(db, admin_user):
    """Create a separate approved resource for recommendations/bookmarks."""
    return Resource.objects.create(
        title="Public Material",
        resource_type="tutorial",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )


@pytest.mark.django_db
class TestDashboardModule:
    """Dashboard endpoints should aggregate user-specific data."""

    def test_dashboard_requires_authentication(self, api_client):
        response = api_client.get("/api/dashboard/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_returns_expected_sections(self, authenticated_client):
        response = authenticated_client.get("/api/dashboard/")
        assert response.status_code == status.HTTP_200_OK
        assert "user_summary" in response.data
        assert "quick_stats" in response.data
        assert "recent_activity" in response.data
        assert "recommendations" in response.data
        assert "announcements" in response.data
        assert "pending_uploads" in response.data
        assert "notifications" in response.data

    def test_dashboard_stats_reflect_upload_download_and_bookmark_counts(
        self, authenticated_client, user, dashboard_resource, public_resource
    ):
        Bookmark.objects.create(user=user, resource=public_resource)
        Download.objects.create(user=user, resource=dashboard_resource)

        response = authenticated_client.get("/api/dashboard/stats/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["uploads_count"] >= 1
        assert response.data["downloads_count"] == 1
        assert response.data["bookmarks_count"] == 1

    def test_dashboard_activity_endpoint_returns_recent_lists(
        self, authenticated_client, user, dashboard_resource, public_resource
    ):
        Bookmark.objects.create(user=user, resource=public_resource)
        Download.objects.create(user=user, resource=dashboard_resource)

        response = authenticated_client.get("/api/dashboard/activity/")
        assert response.status_code == status.HTTP_200_OK
        assert "recent_uploads" in response.data
        assert "recent_downloads" in response.data
        assert "recent_bookmarks" in response.data
        assert len(response.data["recent_uploads"]) >= 1
        assert len(response.data["recent_downloads"]) >= 1
        assert len(response.data["recent_bookmarks"]) >= 1

    def test_dashboard_recommendations_endpoint_returns_sections(
        self, authenticated_client, public_resource
    ):
        response = authenticated_client.get("/api/dashboard/recommendations/")
        assert response.status_code == status.HTTP_200_OK
        assert "for_you" in response.data
        assert "trending" in response.data
        assert "course_related" in response.data
        assert "recently_added" in response.data
