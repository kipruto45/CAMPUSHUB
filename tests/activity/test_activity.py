"""Tests for activity module."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.activity.models import ActivityType, RecentActivity
from apps.activity.services import ActivityService
from apps.bookmarks.models import Bookmark
from apps.resources.models import PersonalResource, Resource


@pytest.fixture
def resource(db, admin_user):
    """Create a public approved resource."""
    return Resource.objects.create(
        title="Viewed Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        file=SimpleUploadedFile("viewed.pdf", b"pdf-content"),
    )


@pytest.fixture
def personal_file(db, user):
    """Create a personal file for open/download activity."""
    return PersonalResource.objects.create(
        user=user,
        title="Private File",
        file=SimpleUploadedFile("private.pdf", b"pdf-content"),
    )


@pytest.mark.django_db
class TestActivityModule:
    """Activity API and deduplication tests."""

    def test_log_resource_view_deduplicates_within_window(
        self, user, resource
    ):
        first = ActivityService.log_resource_view(user=user, resource=resource)
        second = ActivityService.log_resource_view(
            user=user,
            resource=resource,
        )
        assert first.id == second.id
        assert (
            RecentActivity.objects.filter(
                user=user,
                resource=resource,
                activity_type=ActivityType.VIEWED_RESOURCE,
            ).count()
            == 1
        )

    def test_log_download_deduplicates_short_window(self, user, resource):
        first = ActivityService.log_download(user=user, resource=resource)
        second = ActivityService.log_download(user=user, resource=resource)
        assert first.id == second.id
        assert (
            RecentActivity.objects.filter(
                user=user,
                resource=resource,
                activity_type=ActivityType.DOWNLOADED_RESOURCE,
            ).count()
            == 1
        )

    def test_unified_recent_endpoint_returns_user_activity(
        self, authenticated_client, user, resource
    ):
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )
        response = authenticated_client.get(reverse("activity:unified-recent"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 1

    def test_recent_resources_and_files_filters(
        self, authenticated_client, user, resource, personal_file
    ):
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )
        RecentActivity.objects.create(
            user=user,
            personal_file=personal_file,
            activity_type=ActivityType.OPENED_PERSONAL_FILE,
        )
        resources_response = authenticated_client.get(
            reverse("activity:recent-resources")
        )
        files_response = authenticated_client.get(
            reverse("activity:recent-files")
        )
        assert resources_response.status_code == status.HTTP_200_OK
        assert files_response.status_code == status.HTTP_200_OK
        assert resources_response.data["count"] == 1
        assert files_response.data["count"] == 1

    def test_recent_bookmarks_endpoint(
        self, authenticated_client, user, resource
    ):
        bookmark = Bookmark.objects.create(user=user, resource=resource)
        ActivityService.log_bookmark(user=user, bookmark=bookmark)
        response = authenticated_client.get(
            reverse("activity:recent-bookmarks")
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_activity_stats_counts_all_types(
        self, authenticated_client, user, resource
    ):
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.DOWNLOADED_RESOURCE,
        )
        response = authenticated_client.get(reverse("activity:activity-stats"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_activities"] >= 2
        assert response.data["viewed_count"] >= 1
        assert response.data["downloaded_count"] >= 1

    def test_clear_old_activities_removes_stale_records(
        self, authenticated_client, user, resource
    ):
        stale = RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )
        fresh = RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.DOWNLOADED_RESOURCE,
        )
        RecentActivity.objects.filter(id=stale.id).update(
            created_at=timezone.now() - timedelta(days=120)
        )
        RecentActivity.objects.filter(id=fresh.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        response = authenticated_client.delete(
            f"{reverse('activity:clear-old')}?days=90"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted_count"] >= 1
        assert RecentActivity.objects.filter(id=fresh.id).exists()
        assert not RecentActivity.objects.filter(id=stale.id).exists()

    def test_unauthenticated_user_cannot_access_activity(self, api_client):
        response = api_client.get(reverse("activity:unified-recent"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
