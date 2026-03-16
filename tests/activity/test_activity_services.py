"""Service-level tests for activity module."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.activity.models import ActivityType, RecentActivity
from apps.activity.services import ActivityService
from apps.bookmarks.models import Bookmark
from apps.resources.models import PersonalResource, Resource


@pytest.fixture
def request_with_meta():
    """Request object carrying network metadata."""
    return APIRequestFactory().get("/", REMOTE_ADDR="127.0.0.1")


@pytest.fixture
def resource(db, admin_user):
    """Create approved resource for activity service tests."""
    return Resource.objects.create(
        title="Activity Service Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        file=SimpleUploadedFile("activity-resource.pdf", b"pdf-content"),
    )


@pytest.fixture
def personal_file(db, user):
    """Create personal file for activity service tests."""
    return PersonalResource.objects.create(
        user=user,
        title="Activity Service Personal",
        file=SimpleUploadedFile("activity-personal.pdf", b"pdf-content"),
    )


@pytest.mark.django_db
class TestActivityService:
    """Direct service tests for branch-heavy activity logic."""

    def test_log_personal_file_open_with_and_without_request(
        self, user, personal_file, request_with_meta
    ):
        first = ActivityService.log_personal_file_open(
            user=user,
            personal_file=personal_file,
            request=request_with_meta,
        )
        second = ActivityService.log_personal_file_open(
            user=user,
            personal_file=personal_file,
        )
        assert first.id == second.id
        assert first.ip_address == "127.0.0.1"

    def test_log_download_personal_file_branch(self, user, personal_file):
        activity = ActivityService.log_download(
            user=user,
            personal_file=personal_file,
        )
        assert activity.activity_type == ActivityType.DOWNLOADED_PERSONAL_FILE

    def test_log_bookmark_dedup(self, user, resource):
        bookmark = Bookmark.objects.create(user=user, resource=resource)
        first = ActivityService.log_bookmark(user=user, bookmark=bookmark)
        second = ActivityService.log_bookmark(user=user, bookmark=bookmark)
        assert first.id == second.id

    def test_get_recent_helpers_return_filtered_results(
        self, user, resource, personal_file
    ):
        bookmark = Bookmark.objects.create(user=user, resource=resource)
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
        RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.DOWNLOADED_RESOURCE,
        )
        RecentActivity.objects.create(
            user=user,
            bookmark=bookmark,
            resource=resource,
            activity_type=ActivityType.BOOKMARKED_RESOURCE,
        )

        assert ActivityService.get_recent_activities(
            user,
            limit=10,
        ).count() >= 4
        assert ActivityService.get_recent_resources(
            user,
            limit=10,
        ).count() == 1
        assert ActivityService.get_recent_personal_files(
            user,
            limit=10,
        ).count() == 1
        assert ActivityService.get_recent_downloads(
            user,
            limit=10,
        ).count() == 1
        assert (
            ActivityService.get_recent_activities(
                user,
                limit=10,
                activity_type=ActivityType.BOOKMARKED_RESOURCE,
            ).count()
            >= 1
        )

    def test_clear_old_activities_service(self, user, resource):
        stale = RecentActivity.objects.create(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
        )
        RecentActivity.objects.filter(id=stale.id).update(
            created_at=timezone.now() - timedelta(days=180)
        )
        deleted = ActivityService.clear_old_activities(user=user, days=90)
        assert deleted >= 1
        assert not RecentActivity.objects.filter(id=stale.id).exists()
