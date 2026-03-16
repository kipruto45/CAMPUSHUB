"""Tests for downloads module."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from apps.activity.models import ActivityType, RecentActivity
from apps.downloads.models import Download
from apps.resources.models import PersonalResource, Resource

User = get_user_model()


@pytest.fixture
def downloadable_resource(db, admin_user):
    """Create an approved resource with a file."""
    return Resource.objects.create(
        title="Downloadable Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        file=SimpleUploadedFile("resource.pdf", b"pdf-content"),
    )


@pytest.fixture
def pending_resource(db, admin_user):
    """Create a pending resource that should not be downloadable."""
    return Resource.objects.create(
        title="Pending Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="pending",
        is_public=True,
        file=SimpleUploadedFile("pending.pdf", b"pdf-content"),
    )


@pytest.fixture
def personal_file(db, user):
    """Create a user-owned personal file."""
    return PersonalResource.objects.create(
        user=user,
        title="My Personal File",
        file=SimpleUploadedFile("personal.txt", b"file-content"),
    )


@pytest.mark.django_db
class TestDownloadsModule:
    """Downloads workflow, visibility, and stats tests."""

    def test_download_resource_creates_record_and_increments_count(
        self, authenticated_client, user, downloadable_resource
    ):
        response = authenticated_client.post(
            reverse(
                "downloads:download-resource",
                kwargs={"resource_id": downloadable_resource.id},
            ),
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        downloadable_resource.refresh_from_db()
        assert downloadable_resource.download_count == 1
        assert Download.objects.filter(
            user=user,
            resource=downloadable_resource,
        ).exists()
        assert RecentActivity.objects.filter(
            user=user,
            resource=downloadable_resource,
            activity_type=ActivityType.DOWNLOADED_RESOURCE,
        ).exists()

    def test_download_resource_rejects_non_approved(
        self, authenticated_client, pending_resource
    ):
        response = authenticated_client.post(
            reverse(
                "downloads:download-resource",
                kwargs={"resource_id": pending_resource.id},
            ),
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_personal_file_owned_by_user(
        self, authenticated_client, user, personal_file
    ):
        response = authenticated_client.post(
            reverse(
                "downloads:download-personal-file",
                kwargs={"file_id": personal_file.id},
            ),
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert Download.objects.filter(
            user=user,
            personal_file=personal_file,
        ).exists()
        assert RecentActivity.objects.filter(
            user=user,
            personal_file=personal_file,
            activity_type=ActivityType.DOWNLOADED_PERSONAL_FILE,
        ).exists()

    def test_download_personal_file_denies_non_owner(
        self, api_client, personal_file
    ):
        other_user = User.objects.create_user(
            email="downloads-other@test.com",
            password="testpass123",
            full_name="Other User",
            registration_number="DWN001",
            role="student",
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.post(
            reverse(
                "downloads:download-personal-file",
                kwargs={"file_id": personal_file.id},
            ),
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_history_shows_only_current_user_records(
        self, authenticated_client, user, downloadable_resource
    ):
        other_user = User.objects.create_user(
            email="downloads-other-2@test.com",
            password="testpass123",
            full_name="Other User 2",
            registration_number="DWN002",
            role="student",
        )
        Download.objects.create(user=user, resource=downloadable_resource)
        Download.objects.create(
            user=other_user,
            resource=downloadable_resource,
        )

        response = authenticated_client.get(
            reverse("downloads:download-history-list")
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_download_check_and_count_endpoints(
        self, authenticated_client, user, downloadable_resource
    ):
        check_before = authenticated_client.get(
            reverse(
                "downloads:resource-download-check",
                kwargs={"resource_id": downloadable_resource.id},
            )
        )
        assert check_before.status_code == status.HTTP_200_OK
        assert check_before.data["has_downloaded"] is False

        Download.objects.create(user=user, resource=downloadable_resource)
        downloadable_resource.download_count = 1
        downloadable_resource.save(update_fields=["download_count"])

        count_response = authenticated_client.get(
            reverse(
                "downloads:resource-download-count",
                kwargs={"resource_id": downloadable_resource.id},
            )
        )
        assert count_response.status_code == status.HTTP_200_OK
        assert count_response.data["download_count"] == 1

        check_after = authenticated_client.get(
            reverse(
                "downloads:resource-download-check",
                kwargs={"resource_id": downloadable_resource.id},
            )
        )
        assert check_after.status_code == status.HTTP_200_OK
        assert check_after.data["has_downloaded"] is True

    def test_recent_and_stats_endpoints_return_expected_shape(
        self, authenticated_client, user, downloadable_resource
    ):
        Download.objects.create(user=user, resource=downloadable_resource)
        recent_response = authenticated_client.get(
            reverse("downloads:recent-downloads")
        )
        assert recent_response.status_code == status.HTTP_200_OK
        assert len(recent_response.data) >= 1

        stats_response = authenticated_client.get(
            reverse("downloads:download-stats")
        )
        assert stats_response.status_code == status.HTTP_200_OK
        assert stats_response.data["total_downloads"] >= 1
        assert "recent_downloads" in stats_response.data

    def test_unauthenticated_user_cannot_access_history(self, api_client):
        response = api_client.get(reverse("downloads:download-history-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
