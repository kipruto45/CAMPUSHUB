"""Tests for resources service-layer classes."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.ratings.models import Rating
from apps.reports.models import Report
from apps.resources.models import (Folder, FolderItem, PersonalResource, Resource,
                                   ResourceShareEvent, UserStorage)
from apps.resources.services import (ResourceBookmarkService,
                                     ResourceDetailService,
                                     ResourceDownloadService,
                                     ResourceRatingService,
                                     ResourceReportService,
                                     ResourceShareService,
                                     ResourceUploadService)


def _upload_file(name="notes.pdf", size=1024, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"a" * size, content_type=content_type)


def _resource(owner, course=None, unit=None, **overrides):
    defaults = {
        "title": "Service Resource",
        "resource_type": "notes",
        "uploaded_by": owner,
        "status": "approved",
        "is_public": True,
        "course": course,
        "unit": unit,
    }
    defaults.update(overrides)
    return Resource.objects.create(**defaults)


@pytest.mark.django_db
def test_resource_detail_service_user_specific_data(
    user,
    admin_user,
    course,
    unit,
):
    resource = _resource(
        admin_user,
        course=course,
        unit=unit,
        tags="trees,graphs",
    )
    anonymous_data = ResourceDetailService(resource).get_user_specific_data()
    assert anonymous_data["can_download"] is True
    assert anonymous_data["is_bookmarked"] is False

    Bookmark.objects.create(user=user, resource=resource)
    Favorite.objects.create(
        user=user,
        favorite_type=FavoriteType.RESOURCE,
        resource=resource,
    )
    folder = Folder.objects.create(user=user, name="My Library")
    FolderItem.objects.create(folder=folder, resource=resource)
    Rating.objects.create(user=user, resource=resource, value=5)

    user_data = ResourceDetailService(resource, user=user).get_user_specific_data()
    assert user_data["is_bookmarked"] is True
    assert user_data["is_favorited"] is True
    assert user_data["is_in_my_library"] is True
    assert user_data["user_rating"] == 5
    assert user_data["can_download"] is True
    assert user_data["can_edit"] is False


@pytest.mark.django_db
def test_resource_detail_track_view_and_related(user, admin_user, course, unit):
    target = _resource(
        admin_user,
        course=course,
        unit=unit,
        title="Data Structures",
        tags="trees,queues",
        resource_type="notes",
        view_count=1,
        download_count=1,
    )
    related = _resource(
        admin_user,
        course=course,
        unit=unit,
        title="Data Structures Practice",
        tags="trees,graphs",
        resource_type="notes",
    )
    unrelated = _resource(
        admin_user,
        title="History Essay",
        resource_type="book",
        tags="history",
    )

    service = ResourceDetailService(target, user=user)
    with patch("apps.activity.services.ActivityService.log_resource_view") as mocked:
        service.track_view()
    target.refresh_from_db()

    rows = service.get_related_resources(limit=5)
    ids = [row.id for row in rows]

    assert target.view_count == 2
    mocked.assert_called_once()
    assert related.id in ids
    assert unrelated.id not in ids


@pytest.mark.django_db
def test_resource_download_service_permissions_and_recording(
    user,
    admin_user,
    course,
):
    approved = _resource(admin_user, course=course, title="Approved")
    pending = _resource(
        admin_user,
        course=course,
        title="Pending",
        status="pending",
    )

    anonymous_service = ResourceDownloadService(approved, user=None)
    can_download, error = anonymous_service.can_download()
    assert can_download is True and error is None

    blocked_service = ResourceDownloadService(pending, user=None)
    can_download, error = blocked_service.can_download()
    assert can_download is False and error is not None

    user_service = ResourceDownloadService(approved, user=user)
    request = APIRequestFactory().get("/api/resources/")
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8"
    assert user_service.record_download(request) is True
    approved.refresh_from_db()
    assert approved.download_count >= 1
    assert Download.objects.filter(user=user, resource=approved).exists()


@pytest.mark.django_db
def test_bookmark_service_add_to_library(user, admin_user, course):
    resource = _resource(admin_user, course=course, title="Library Candidate")
    service = ResourceBookmarkService(resource, user)

    created = service.add_to_library()
    duplicate = service.add_to_library()
    invalid = service.add_to_library(folder_id="00000000-0000-0000-0000-000000000000")

    assert created["success"] is True
    assert duplicate["success"] is False
    assert invalid["success"] is False


@pytest.mark.django_db
def test_rating_and_report_services(user, admin_user, course):
    resource = _resource(admin_user, course=course, title="Rate Me")
    rating_service = ResourceRatingService(resource, user)

    invalid = rating_service.rate(0)
    saved = rating_service.rate(4)
    removed = rating_service.remove_rating()
    missing_remove = rating_service.remove_rating()

    own_service = ResourceRatingService(resource, admin_user)
    own_rate = own_service.rate(5)

    report_service = ResourceReportService(resource, user)
    report_one = report_service.report("spam", "Looks suspicious")
    report_two = report_service.report("spam", "Duplicate report")

    resource.refresh_from_db()

    assert invalid["success"] is False
    assert saved["success"] is True
    assert removed["success"] is True
    assert missing_remove["success"] is False
    assert own_rate["success"] is False
    assert report_one["success"] is True
    assert report_two["success"] is False
    assert Report.objects.filter(reporter=user, resource=resource).count() == 1


@pytest.mark.django_db
def test_upload_validation_requires_title_file_and_metadata(user, course, unit):
    with pytest.raises(ValidationError):
        ResourceUploadService.validate_resource_upload(
            user=user,
            data={},
            file_obj=None,
        )

    with pytest.raises(ValidationError):
        ResourceUploadService.validate_resource_upload(
            user=user,
            data={"title": "My Upload"},
            file_obj=_upload_file("notes.pdf"),
        )

    faculty = course.department.faculty
    valid = ResourceUploadService.validate_resource_upload(
        user=user,
        data={
            "title": "  My   Upload  ",
            "tags": "Trees, trees, Graphs",
            "faculty": faculty,
            "department": course.department,
            "course": course,
            "unit": unit,
            "semester": "1",
            "year_of_study": 2,
        },
        file_obj=_upload_file("My Notes.pdf"),
    )

    assert valid["title"] == "My Upload"
    assert valid["file_type"] == "pdf"
    assert "my_notes.pdf" in valid["normalized_filename"]


@pytest.mark.django_db
def test_create_update_upload_and_recalculate_storage(
    user,
    admin_user,
    moderator_user,
    faculty,
    department,
    course,
    unit,
):
    data = {
        "file": _upload_file("algorithms.pdf", size=2048),
        "title": "Algorithms Notes",
        "description": "content",
        "resource_type": "notes",
        "faculty": faculty,
        "department": department,
        "course": course,
        "unit": unit,
        "semester": "1",
        "year_of_study": 2,
        "tags": "",
    }

    with patch(
        "apps.resources.services.NotificationService.create_notification"
    ) as notify_mock:
        resource = ResourceUploadService.create_resource_upload(
            user=user,
            validated_data=data.copy(),
        )

    assert resource.status == "pending"
    assert resource.uploaded_by_id == user.id
    assert resource.tags != ""
    assert notify_mock.call_count >= 2  # admin + moderator

    resource.status = "rejected"
    resource.rejection_reason = "Wrong metadata"
    resource.save(update_fields=["status", "rejection_reason"])

    updated = ResourceUploadService.update_resource_upload(
        instance=resource,
        user=user,
        validated_data={"title": "Updated Title"},
    )
    assert updated.status == "pending"
    assert updated.rejection_reason == ""
    assert updated.title == "Updated Title"

    uploads = ResourceUploadService.get_user_uploads(user)
    assert uploads.first().id == resource.id

    personal_file = PersonalResource.objects.create(
        user=user,
        title="Personal File",
        file=_upload_file("personal.pdf", size=1024),
        file_size=1024,
    )
    assert personal_file.id

    ResourceUploadService.recalculate_user_storage_usage(user)
    storage = UserStorage.objects.get(user=user)
    assert storage.used_storage >= resource.file_size + 1024
    assert storage.updated_at <= timezone.now()


@pytest.mark.django_db
def test_resource_share_service_payload_and_recording(user, admin_user, course):
    resource = _resource(
        admin_user,
        course=course,
        title="Data Structures Notes",
        status="approved",
        is_public=True,
        share_count=0,
    )
    service = ResourceShareService(resource, user=user)

    payload = service.get_share_payload()
    assert payload["can_share"] is True
    assert str(resource.slug) in payload["share_url"]
    assert "Check out this resource on CampusHub:" in payload["share_message"]

    request = APIRequestFactory().post("/api/resources/")
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["HTTP_USER_AGENT"] = "pytest-share-agent"
    result = service.record_share(method=ResourceShareEvent.ShareMethod.COPY_LINK, request=request)

    resource.refresh_from_db()
    assert result["success"] is True
    assert resource.share_count == 1
    assert ResourceShareEvent.objects.filter(
        resource=resource,
        user=user,
        share_method=ResourceShareEvent.ShareMethod.COPY_LINK,
    ).exists()


@pytest.mark.django_db
def test_resource_share_service_blocks_non_shareable(admin_user, course):
    pending = _resource(
        admin_user,
        course=course,
        title="Pending Resource",
        status="pending",
        is_public=True,
    )
    private = _resource(
        admin_user,
        course=course,
        title="Private Resource",
        status="approved",
        is_public=False,
    )

    can_share_pending, pending_reason = ResourceShareService.can_share(pending)
    can_share_private, private_reason = ResourceShareService.can_share(private)

    assert can_share_pending is False
    assert "approved" in str(pending_reason).lower()
    assert can_share_private is False
    assert "private" in str(private_reason).lower()
