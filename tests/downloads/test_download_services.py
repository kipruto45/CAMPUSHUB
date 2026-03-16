"""Service-level tests for downloads module."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from apps.downloads.models import Download
from apps.downloads.services import DownloadService
from apps.resources.models import PersonalResource, Resource


@pytest.fixture
def request_with_meta():
    """Request object with IP and user agent metadata."""
    request = APIRequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="10.10.10.1",
        HTTP_USER_AGENT="pytest-agent",
    )
    return request


@pytest.fixture
def approved_resource(db, admin_user):
    """Create approved resource with file."""
    return Resource.objects.create(
        title="Service Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        file=SimpleUploadedFile("service-resource.pdf", b"pdf-content"),
    )


@pytest.fixture
def pending_resource(db, admin_user):
    """Create non-approved resource."""
    return Resource.objects.create(
        title="Pending Service Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="pending",
        is_public=True,
        file=SimpleUploadedFile("pending-service.pdf", b"pdf-content"),
    )


@pytest.fixture
def personal_file(db, user):
    """Create personal file for service tests."""
    return PersonalResource.objects.create(
        user=user,
        title="Service Personal File",
        file=SimpleUploadedFile("service-personal.pdf", b"pdf-content"),
    )


@pytest.mark.django_db
class TestDownloadService:
    """Direct business logic tests for download service methods."""

    def test_download_public_resource_success(
        self, user, approved_resource, request_with_meta
    ):
        result = DownloadService.download_public_resource(
            user=user,
            resource=approved_resource,
            request=request_with_meta,
        )
        approved_resource.refresh_from_db()
        download = Download.objects.get(id=result["download_id"])

        assert approved_resource.download_count == 1
        assert download.ip_address == "10.10.10.1"
        assert download.user_agent == "pytest-agent"
        assert result["resource_title"] == approved_resource.title

    def test_download_public_resource_rejects_non_approved(
        self, user, pending_resource, request_with_meta
    ):
        with pytest.raises(ValueError, match="not available for download"):
            DownloadService.download_public_resource(
                user=user,
                resource=pending_resource,
                request=request_with_meta,
            )

    def test_download_public_resource_requires_file(
        self, user, admin_user, request_with_meta
    ):
        resource_without_file = Resource.objects.create(
            title="No File Resource",
            resource_type="notes",
            uploaded_by=admin_user,
            status="approved",
            is_public=True,
            file=None,
        )
        with pytest.raises(ValueError, match="File not available"):
            DownloadService.download_public_resource(
                user=user,
                resource=resource_without_file,
                request=request_with_meta,
            )

    def test_download_personal_file_success(
        self, user, personal_file, request_with_meta
    ):
        result = DownloadService.download_personal_file(
            user=user,
            personal_file=personal_file,
            request=request_with_meta,
        )
        download = Download.objects.get(id=result["download_id"])
        assert download.personal_file == personal_file
        assert download.ip_address == "10.10.10.1"
        assert result["file_name"].startswith("service-personal")
        assert result["file_name"].endswith(".pdf")

    def test_download_personal_file_rejects_non_owner(
        self, admin_user, personal_file, request_with_meta
    ):
        with pytest.raises(PermissionError, match="do not have permission"):
            DownloadService.download_personal_file(
                user=admin_user,
                personal_file=personal_file,
                request=request_with_meta,
            )

    def test_download_personal_file_requires_file(
        self, user, request_with_meta
    ):
        fileless_personal = PersonalResource.objects.create(
            user=user,
            title="Missing File",
            file=SimpleUploadedFile("placeholder.txt", b"x"),
        )
        fileless_personal.file.delete(save=False)
        fileless_personal.file = None
        fileless_personal.save(update_fields=["file"])

        with pytest.raises(ValueError, match="File not available"):
            DownloadService.download_personal_file(
                user=user,
                personal_file=fileless_personal,
                request=request_with_meta,
            )

    def test_stats_and_lookup_helpers(
        self, user, approved_resource, request_with_meta
    ):
        DownloadService.download_public_resource(
            user=user,
            resource=approved_resource,
            request=request_with_meta,
        )
        stats = DownloadService.get_user_download_stats(user)
        history = DownloadService.get_user_download_history(user, limit=1)
        top_resources = DownloadService.get_most_downloaded_resources(limit=1)

        assert stats["total_downloads"] >= 1
        assert stats["unique_resources"] >= 1
        assert history.count() == 1
        assert top_resources[0].id == approved_resource.id
        assert DownloadService.is_resource_downloaded_by_user(
            user=user,
            resource=approved_resource,
        )
