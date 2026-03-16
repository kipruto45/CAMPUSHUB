"""Tests for mobile feature endpoints added for app parity."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.resources.models import PersonalFolder, PersonalResource, Resource


@pytest.fixture
def approved_resource(user, faculty, department, course, unit):
    """Create an approved public resource with a file."""
    upload = SimpleUploadedFile(
        "approved_resource.pdf",
        b"%PDF-1.4 approved resource",
        content_type="application/pdf",
    )
    return Resource.objects.create(
        title="Approved Resource",
        description="A public approved file",
        resource_type="notes",
        file=upload,
        faculty=faculty,
        department=department,
        course=course,
        unit=unit,
        semester="1",
        year_of_study=2,
        tags="approved,notes",
        uploaded_by=user,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def other_user(db):
    """Create a second user for access tests."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_user(
        email="other@test.com",
        password="testpass123",
        full_name="Other Student",
        registration_number="STU002",
        role="student",
    )


@pytest.mark.django_db
def test_mobile_upload_resource_creates_pending(
    authenticated_client, faculty, department, course, unit, user
):
    url = reverse("api:mobile_upload_resource")
    file_obj = SimpleUploadedFile(
        "mobile_upload_notes.pdf",
        b"%PDF-1.4 mobile upload",
        content_type="application/pdf",
    )
    data = {
        "description": "Uploaded from mobile flow",
        "resource_type": "notes",
        "file": file_obj,
        "faculty": str(faculty.id),
        "department": str(department.id),
        "course": str(course.id),
        "unit": str(unit.id),
        "semester": "1",
        "year_of_study": 2,
        "tags": "mobile,upload",
    }

    response = authenticated_client.post(url, data, format="multipart")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["data"]["status"] == "pending"
    created = Resource.objects.get(id=response.data["data"]["resource"]["id"])
    assert created.uploaded_by_id == user.id
    assert created.status == "pending"
    assert created.title == "Mobile Upload Notes"


@pytest.mark.django_db
def test_mobile_bookmark_toggle_and_list(authenticated_client, approved_resource):
    toggle_url = reverse(
        "api:mobile_toggle_bookmark", kwargs={"resource_id": approved_resource.id}
    )
    list_url = reverse("api:mobile_bookmarks")

    add_response = authenticated_client.post(toggle_url, {}, format="json")
    assert add_response.status_code == status.HTTP_200_OK
    assert add_response.data["data"]["is_bookmarked"] is True
    assert Bookmark.objects.filter(resource=approved_resource).count() == 1

    list_response = authenticated_client.get(list_url)
    assert list_response.status_code == status.HTTP_200_OK
    bookmark_items = list_response.data["data"]["bookmarks"]
    assert len(bookmark_items) == 1
    assert str(bookmark_items[0]["resource"]["id"]) == str(approved_resource.id)

    remove_response = authenticated_client.post(toggle_url, {}, format="json")
    assert remove_response.status_code == status.HTTP_200_OK
    assert remove_response.data["data"]["is_bookmarked"] is False
    assert Bookmark.objects.filter(resource=approved_resource).count() == 0


@pytest.mark.django_db
def test_mobile_bookmark_toggle_rejects_non_visible_resource(
    authenticated_client, other_user, course
):
    blocked = Resource.objects.create(
        title="Pending Hidden Resource",
        resource_type="notes",
        uploaded_by=other_user,
        course=course,
        status="pending",
        is_public=True,
    )
    url = reverse("api:mobile_toggle_bookmark", kwargs={"resource_id": blocked.id})

    response = authenticated_client.post(url, {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "BOOKMARK_NOT_ALLOWED"


@pytest.mark.django_db
def test_mobile_favorite_toggle_and_list(authenticated_client, approved_resource):
    toggle_url = reverse(
        "api:mobile_toggle_favorite", kwargs={"resource_id": approved_resource.id}
    )
    list_url = reverse("api:mobile_favorites")

    add_response = authenticated_client.post(toggle_url, {}, format="json")
    assert add_response.status_code == status.HTTP_200_OK
    assert add_response.data["data"]["is_favorited"] is True
    assert (
        Favorite.objects.filter(
            user=approved_resource.uploaded_by,
            favorite_type=FavoriteType.RESOURCE,
            resource=approved_resource,
        ).count()
        == 1
    )

    list_response = authenticated_client.get(list_url)
    assert list_response.status_code == status.HTTP_200_OK
    favorite_items = list_response.data["data"]["favorites"]
    assert len(favorite_items) == 1
    assert str(favorite_items[0]["resource"]["id"]) == str(approved_resource.id)


@pytest.mark.django_db
def test_mobile_download_resource_is_idempotent(
    authenticated_client, approved_resource
):
    url = reverse(
        "api:mobile_download_resource", kwargs={"resource_id": approved_resource.id}
    )
    headers = {"HTTP_X_IDEMPOTENCY_KEY": "mobile-download-1"}

    first = authenticated_client.post(url, {}, format="json", **headers)
    second = authenticated_client.post(url, {}, format="json", **headers)

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert first["X-Idempotent-Replay"] == "false"
    assert second["X-Idempotent-Replay"] == "true"
    assert Download.objects.filter(resource=approved_resource).count() == 1
    approved_resource.refresh_from_db()
    assert approved_resource.download_count == 1


@pytest.mark.django_db
def test_mobile_save_to_library_creates_copy_and_prevents_duplicate(
    authenticated_client, approved_resource, user
):
    url = reverse(
        "api:mobile_save_to_library", kwargs={"resource_id": approved_resource.id}
    )

    first = authenticated_client.post(url, {}, format="json")
    assert first.status_code == status.HTTP_200_OK
    assert first.data["data"]["already_saved"] is False
    assert (
        PersonalResource.objects.filter(
            user=user, linked_public_resource=approved_resource
        ).count()
        == 1
    )

    second = authenticated_client.post(url, {}, format="json")
    assert second.status_code == status.HTTP_200_OK
    assert second.data["data"]["already_saved"] is True
    assert (
        PersonalResource.objects.filter(
            user=user, linked_public_resource=approved_resource
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_mobile_library_summary_and_file_listing_are_user_scoped(
    authenticated_client, user, other_user
):
    user_file = SimpleUploadedFile(
        "user_file.pdf", b"%PDF-1.4 my file", content_type="application/pdf"
    )
    other_file = SimpleUploadedFile(
        "other_file.pdf", b"%PDF-1.4 their file", content_type="application/pdf"
    )
    folder = PersonalFolder.objects.create(user=user, name="Semester 1")
    PersonalResource.objects.create(
        user=user,
        folder=folder,
        title="Data Structures",
        file=user_file,
        source_type="uploaded",
    )
    PersonalResource.objects.create(
        user=other_user,
        title="Private Resource",
        file=other_file,
        source_type="uploaded",
    )

    summary_url = reverse("api:mobile_library_summary")
    files_url = reverse("api:mobile_library_files")

    summary_response = authenticated_client.get(summary_url)
    assert summary_response.status_code == status.HTTP_200_OK
    summary = summary_response.data["data"]["summary"]
    assert summary["total_files"] == PersonalResource.objects.filter(user=user).count()
    assert summary["total_folders"] == PersonalFolder.objects.filter(user=user).count()

    files_response = authenticated_client.get(files_url)
    assert files_response.status_code == status.HTTP_200_OK
    assert files_response.data["data"]["pagination"]["total"] == 1
    assert files_response.data["data"]["files"][0]["title"] == "Data Structures"

    filtered = authenticated_client.get(
        files_url, {"search": "Data", "folder": folder.id}
    )
    assert filtered.status_code == status.HTTP_200_OK
    assert filtered.data["data"]["pagination"]["total"] == 1


@pytest.mark.django_db
def test_mobile_library_folders_support_root_and_parent_filters(
    authenticated_client, user
):
    root = PersonalFolder.objects.create(user=user, name="Root Folder")
    child = PersonalFolder.objects.create(user=user, name="Child Folder", parent=root)
    url = reverse("api:mobile_library_folders")

    root_response = authenticated_client.get(url)
    assert root_response.status_code == status.HTTP_200_OK
    root_ids = [item["id"] for item in root_response.data["data"]["folders"]]
    assert str(root.id) in root_ids
    assert str(child.id) not in root_ids

    child_response = authenticated_client.get(url, {"parent": root.id})
    assert child_response.status_code == status.HTTP_200_OK
    child_ids = [item["id"] for item in child_response.data["data"]["folders"]]
    assert str(child.id) in child_ids


@pytest.mark.django_db
def test_mobile_student_workflow_end_to_end(
    authenticated_client,
    user,
    admin_user,
    faculty,
    department,
    course,
    unit,
):
    """Validate the core student mobile workflow as a single journey."""
    approved = Resource.objects.create(
        title="Algorithms Week 1",
        description="Approved learning material",
        resource_type="notes",
        file=SimpleUploadedFile(
            "algorithms_week_1.pdf",
            b"%PDF-1.4 approved notes",
            content_type="application/pdf",
        ),
        faculty=faculty,
        department=department,
        course=course,
        unit=unit,
        semester="1",
        year_of_study=2,
        tags="algorithms,week1",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )

    dashboard = authenticated_client.get(reverse("api:mobile_dashboard"))
    assert dashboard.status_code == status.HTTP_200_OK
    assert "stats" in dashboard.data["data"]

    resources_response = authenticated_client.get(reverse("api:mobile_resources"))
    assert resources_response.status_code == status.HTTP_200_OK
    listed_ids = {
        str(item["id"]) for item in resources_response.data["data"]["resources"]
    }
    assert str(approved.id) in listed_ids

    detail_url = reverse("api:mobile_resource_detail", kwargs={"resource_id": approved.id})
    detail_before = authenticated_client.get(detail_url)
    assert detail_before.status_code == status.HTTP_200_OK
    assert detail_before.data["data"]["is_bookmarked"] is False
    assert detail_before.data["data"]["is_favorited"] is False
    approved.refresh_from_db()
    assert approved.view_count == 1

    bookmark_url = reverse(
        "api:mobile_toggle_bookmark",
        kwargs={"resource_id": approved.id},
    )
    bookmark_add = authenticated_client.post(bookmark_url, {}, format="json")
    assert bookmark_add.status_code == status.HTTP_200_OK
    assert bookmark_add.data["data"]["is_bookmarked"] is True
    assert Bookmark.objects.filter(user=user, resource=approved).exists()

    bookmarks_list = authenticated_client.get(reverse("api:mobile_bookmarks"))
    assert bookmarks_list.status_code == status.HTTP_200_OK
    bookmark_resource_ids = [
        str(item["resource"]["id"])
        for item in bookmarks_list.data["data"]["bookmarks"]
        if item.get("resource")
    ]
    assert str(approved.id) in bookmark_resource_ids

    favorite_url = reverse(
        "api:mobile_toggle_favorite",
        kwargs={"resource_id": approved.id},
    )
    favorite_add = authenticated_client.post(favorite_url, {}, format="json")
    assert favorite_add.status_code == status.HTTP_200_OK
    assert favorite_add.data["data"]["is_favorited"] is True

    favorites_list = authenticated_client.get(reverse("api:mobile_favorites"))
    assert favorites_list.status_code == status.HTTP_200_OK
    favorite_resource_ids = [
        str(item["resource"]["id"])
        for item in favorites_list.data["data"]["favorites"]
        if item.get("resource")
    ]
    assert str(approved.id) in favorite_resource_ids

    download_url = reverse(
        "api:mobile_download_resource",
        kwargs={"resource_id": approved.id},
    )
    download_response = authenticated_client.post(download_url, {}, format="json")
    assert download_response.status_code == status.HTTP_200_OK
    approved.refresh_from_db()
    assert approved.download_count == 1
    assert Download.objects.filter(user=user, resource=approved).count() == 1

    save_url = reverse("api:mobile_save_to_library", kwargs={"resource_id": approved.id})
    save_response = authenticated_client.post(save_url, {}, format="json")
    assert save_response.status_code == status.HTTP_200_OK
    assert save_response.data["data"]["already_saved"] is False
    assert PersonalResource.objects.filter(
        user=user,
        linked_public_resource=approved,
    ).exists()

    summary_response = authenticated_client.get(reverse("api:mobile_library_summary"))
    assert summary_response.status_code == status.HTTP_200_OK
    assert summary_response.data["data"]["summary"]["total_files"] >= 1

    upload_url = reverse("api:mobile_upload_resource")
    upload_response = authenticated_client.post(
        upload_url,
        {
            "description": "Uploaded from student workflow test",
            "resource_type": "notes",
            "file": SimpleUploadedFile(
                "student_workflow_upload.pdf",
                b"%PDF-1.4 mobile upload flow",
                content_type="application/pdf",
            ),
            "faculty": str(faculty.id),
            "department": str(department.id),
            "course": str(course.id),
            "unit": str(unit.id),
            "semester": "1",
            "year_of_study": 2,
            "tags": "student,workflow",
        },
        format="multipart",
    )
    assert upload_response.status_code == status.HTTP_200_OK
    assert upload_response.data["data"]["status"] == "pending"
    upload_id = upload_response.data["data"]["resource"]["id"]

    my_uploads_response = authenticated_client.get(reverse("resources:my-uploads"))
    assert my_uploads_response.status_code == status.HTTP_200_OK
    my_upload_ids = {str(item["id"]) for item in my_uploads_response.data["results"]}
    assert str(upload_id) in my_upload_ids

    update_url = reverse("resources:resource-update", kwargs={"pk": upload_id})
    update_response = authenticated_client.patch(
        update_url, {"title": "Student Workflow Upload Updated"}, format="json"
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.data["title"] == "Student Workflow Upload Updated"

    delete_response = authenticated_client.delete(update_url)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not Resource.objects.filter(id=upload_id).exists()
