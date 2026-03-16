"""Tests for resource automation algorithms."""

from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
from apps.downloads.models import Download
from apps.reports.models import Report
from apps.resources.automations import (calculate_engagement_score,
                                        calculate_moderation_priority,
                                        calculate_recommendation_score,
                                        calculate_search_relevance,
                                        calculate_storage_usage,
                                        calculate_trending_score,
                                        check_storage_limit,
                                        detect_duplicate_file,
                                        get_course_popularity,
                                        get_folder_breadcrumbs,
                                        get_folder_tree,
                                        get_notification_priority,
                                        get_recommended_resources,
                                        get_top_uploaders,
                                        get_trending_resources, suggest_tags,
                                        update_recent_files, validate_file)
from apps.resources.models import (PersonalFolder, PersonalResource, Resource,
                                   UserStorage)


def _upload_file(name="file.pdf", content=b"file-content"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@pytest.mark.django_db
def test_validate_file_checks_extension_and_size():
    valid_file = SimpleNamespace(name="notes.pdf", size=1024)
    invalid_ext = SimpleNamespace(name="script.exe", size=100)
    invalid_size = SimpleNamespace(name="big.pdf", size=60 * 1024 * 1024)

    assert validate_file(valid_file) == (True, None)

    ext_ok, ext_error = validate_file(invalid_ext)
    assert not ext_ok
    assert "not allowed" in ext_error

    size_ok, size_error = validate_file(invalid_size)
    assert not size_ok
    assert "exceeds maximum allowed size" in size_error


@pytest.mark.django_db
def test_detect_duplicate_file_by_filename_or_title(user):
    resource = Resource.objects.create(
        title="Data Structures Notes",
        resource_type="notes",
        uploaded_by=user,
        file=_upload_file("duplicate.pdf"),
        status="approved",
    )

    by_name = detect_duplicate_file(user, resource.file.name)
    by_title = detect_duplicate_file(
        user,
        "different.pdf",
        title=resource.title,
    )
    none_duplicate = detect_duplicate_file(user, "new.pdf", title="Other")

    assert by_name.id == resource.id
    assert by_title.id == resource.id
    assert none_duplicate is None


@pytest.mark.django_db
def test_trending_score_and_trending_resources(user, admin_user, course):
    high = Resource.objects.create(
        title="High",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
        view_count=100,
        download_count=20,
    )
    low = Resource.objects.create(
        title="Low",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        view_count=5,
        download_count=1,
    )
    Bookmark.objects.create(user=admin_user, resource=high)
    Comment.objects.create(user=admin_user, resource=high, content="Great")

    assert calculate_trending_score(high) > calculate_trending_score(low)

    trending = get_trending_resources(limit=2)
    assert trending[0].id == high.id


@pytest.mark.django_db
def test_recommendation_scoring_and_recommendations(user, admin_user, course):
    user.course = course
    user.save(update_fields=["course"])

    interacted = Resource.objects.create(
        title="Interacted",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        average_rating=4.5,
    )
    candidate = Resource.objects.create(
        title="Candidate",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        average_rating=4.0,
        tags="notes,exam",
    )

    Bookmark.objects.create(user=user, resource=interacted)
    Download.objects.create(user=user, resource=interacted)

    assert calculate_recommendation_score(candidate, user) > 0

    recommended = get_recommended_resources(user, limit=5)
    ids = [item.id for item in recommended]
    assert candidate.id in ids
    assert interacted.id not in ids


@pytest.mark.django_db
def test_moderation_priority_search_relevance_and_notification_priority(
    user,
    admin_user,
    course,
):
    resource = Resource.objects.create(
        title="Data Structures Exam Notes",
        description="Exam preparation guide for trees and graphs",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
        view_count=50,
        download_count=10,
        tags="exam,notes,trees",
        average_rating=4.0,
    )
    Report.objects.create(
        reporter=admin_user,
        resource=resource,
        reason_type="copyright",
        message="copyright issue",
    )
    Report.objects.create(
        reporter=admin_user,
        resource=resource,
        reason_type="spam",
        message="spam issue",
    )

    priority = calculate_moderation_priority(resource)
    relevance = calculate_search_relevance(
        resource,
        "data structures exam notes",
    )

    assert priority > 0
    assert relevance > 0
    assert get_notification_priority("resource_approved") == 1
    assert get_notification_priority("unknown") == 5


@pytest.mark.django_db
def test_storage_usage_limit_and_recent_files(user, course):
    public_resource = Resource.objects.create(
        title="Public",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
        file_size=200,
    )
    personal = PersonalResource.objects.create(
        user=user,
        title="Private File",
        file=_upload_file("private.pdf"),
        file_size=100,
    )

    usage = calculate_storage_usage(user)
    assert usage["personal"] >= 100
    assert usage["public"] >= 200
    assert usage["total"] >= 300

    storage = UserStorage.objects.get(user=user)
    storage.storage_limit = usage["total"] + 10
    storage.save(update_fields=["storage_limit"])
    assert check_storage_limit(user, 5) is True
    assert check_storage_limit(user, 20) is False

    assert personal.last_accessed_at is None
    update_recent_files(user, personal)
    personal.refresh_from_db()
    assert personal.last_accessed_at is not None

    update_recent_files(user, public_resource)


@pytest.mark.django_db
def test_tag_suggestions_folder_tree_and_breadcrumbs(user):
    root = PersonalFolder.objects.create(user=user, name="Semester 1")
    child = PersonalFolder.objects.create(
        user=user,
        name="Algorithms",
        parent=root,
    )
    PersonalResource.objects.create(
        user=user,
        folder=child,
        title="Algo Notes",
        file=_upload_file("algo.pdf"),
        file_size=123,
    )

    tags = suggest_tags(
        title="Past Paper Exam Tutorial",
        description="Guide and lab practical",
        resource_type="notes",
    )
    tree = get_folder_tree(user)
    breadcrumbs = get_folder_breadcrumbs(child)

    assert "past paper" in tags
    assert "tutorial" in tags
    assert "lab" in tags
    assert "notes" in tags

    root_node = next(item for item in tree if item["name"] == "Semester 1")
    child_names = [item["name"] for item in root_node["subfolders"]]
    assert "Algorithms" in child_names
    assert breadcrumbs[0]["name"] == "Semester 1"
    assert breadcrumbs[1]["name"] == "Algorithms"


@pytest.mark.django_db
def test_engagement_top_uploaders_and_course_popularity(
    user,
    admin_user,
    course,
):
    resource = Resource.objects.create(
        title="Engagement",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
        view_count=30,
        download_count=7,
        average_rating=4.0,
    )
    Bookmark.objects.create(user=admin_user, resource=resource)
    Comment.objects.create(user=admin_user, resource=resource, content="good")

    score = calculate_engagement_score(resource)
    top_uploaders = get_top_uploaders(days=365, limit=5)
    course_popularity = get_course_popularity()

    assert score > 0
    assert any(item["uploaded_by__id"] == user.id for item in top_uploaders)
    assert any(item["code"] == course.code for item in course_popularity)
