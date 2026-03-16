"""Tests for personal-library and folder endpoints in resources views."""

from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.resources.models import (Folder, FolderItem, PersonalFolder,
                                   PersonalResource, Resource, UserStorage)


@pytest.fixture
def public_resource(user, faculty, department, course, unit):
    """Create a reusable approved public resource."""
    return Resource.objects.create(
        title="Data Structures Notes",
        resource_type="notes",
        uploaded_by=user,
        faculty=faculty,
        department=department,
        course=course,
        unit=unit,
        semester="1",
        year_of_study=2,
        status="approved",
        file=SimpleUploadedFile("ds_notes.pdf", b"%PDF-1.4 sample"),
    )


@pytest.fixture
def personal_folder(user):
    """Create a personal folder for authenticated user."""
    return PersonalFolder.objects.create(user=user, name="Semester 1")


@pytest.fixture
def personal_resource(user, personal_folder):
    """Create a personal resource in user's folder."""
    return PersonalResource.objects.create(
        user=user,
        folder=personal_folder,
        title="Private Notes",
        file=SimpleUploadedFile("private_notes.pdf", b"%PDF-1.4 private"),
        visibility="private",
    )


@pytest.mark.django_db
class TestFolderViewSetActions:
    """Cover shared folder endpoints for saving public resources."""

    def test_add_resource_to_folder_success_and_duplicate(
        self, authenticated_client, public_resource
    ):
        folder = Folder.objects.create(user=public_resource.uploaded_by, name="My Folder")
        url = f"/api/folders/{folder.id}/add_resource/"

        first = authenticated_client.post(
            url, {"resource_id": str(public_resource.id)}, format="json"
        )
        assert first.status_code == status.HTTP_201_CREATED
        assert FolderItem.objects.filter(folder=folder, resource=public_resource).exists()

        second = authenticated_client.post(
            url, {"resource_id": str(public_resource.id)}, format="json"
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_resource_to_folder_not_found(self, authenticated_client, user):
        folder = Folder.objects.create(user=user, name="My Folder")
        url = f"/api/folders/{folder.id}/add_resource/"

        response = authenticated_client.post(
            url, {"resource_id": str(uuid4())}, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_folder_contents_and_remove_resource(
        self, authenticated_client, user, public_resource
    ):
        folder = Folder.objects.create(user=user, name="Coursework")
        FolderItem.objects.create(folder=folder, resource=public_resource)

        contents_response = authenticated_client.get(f"/api/folders/{folder.id}/contents/")
        assert contents_response.status_code == status.HTTP_200_OK
        assert len(contents_response.data) == 1

        remove_response = authenticated_client.delete(
            f"/api/folders/{folder.id}/remove_resource/?resource_id={public_resource.id}"
        )
        assert remove_response.status_code == status.HTTP_200_OK

        missing_response = authenticated_client.delete(
            f"/api/folders/{folder.id}/remove_resource/?resource_id={public_resource.id}"
        )
        assert missing_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestSaveToLibraryViews:
    """Cover save-to-library and save-to-personal-library workflows."""

    def test_save_to_library_creates_default_folder_and_blocks_duplicate(
        self, authenticated_client, public_resource
    ):
        url = reverse("resources:save-to-library", kwargs={"resource_id": public_resource.id})

        first = authenticated_client.post(url, {}, format="json")
        assert first.status_code == status.HTTP_201_CREATED
        assert Folder.objects.filter(user=public_resource.uploaded_by, name="My Library").exists()

        second = authenticated_client.post(url, {}, format="json")
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_save_to_library_returns_404_for_missing_resource(self, authenticated_client):
        url = reverse("resources:save-to-library", kwargs={"resource_id": uuid4()})
        response = authenticated_client.post(url, {}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_save_to_personal_library_success_and_duplicate(
        self, authenticated_client, public_resource, personal_folder
    ):
        url = reverse(
            "resources:save-to-personal-library",
            kwargs={"resource_id": public_resource.id},
        )
        first = authenticated_client.post(
            url,
            {"folder_id": str(personal_folder.id), "title": "Saved Copy"},
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED
        assert first.data["title"] == "Saved Copy"

        second = authenticated_client.post(url, {}, format="json")
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_save_to_personal_library_missing_folder_or_resource(
        self, authenticated_client, public_resource
    ):
        url = reverse(
            "resources:save-to-personal-library",
            kwargs={"resource_id": public_resource.id},
        )
        missing_folder = authenticated_client.post(
            url, {"folder_id": str(uuid4())}, format="json"
        )
        assert missing_folder.status_code == status.HTTP_404_NOT_FOUND

        missing_resource_url = reverse(
            "resources:save-to-personal-library",
            kwargs={"resource_id": uuid4()},
        )
        missing_resource = authenticated_client.post(missing_resource_url, {}, format="json")
        assert missing_resource.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPersonalFolderViewSetActions:
    """Cover personal folder tree, favorites and move validation branches."""

    def test_folder_favorite_toggle_and_favorites_listing(
        self, authenticated_client, personal_folder
    ):
        toggle_url = f"/api/personal-folders/{personal_folder.id}/favorite/"
        first = authenticated_client.post(toggle_url)
        assert first.status_code == status.HTTP_200_OK
        assert first.data["is_favorite"] is True

        second = authenticated_client.post(toggle_url)
        assert second.status_code == status.HTTP_200_OK
        assert second.data["is_favorite"] is False

        authenticated_client.post(toggle_url)
        list_response = authenticated_client.get("/api/personal-folders/favorites/")
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.data) == 1

    def test_tree_and_contents_actions(self, authenticated_client, user):
        root = PersonalFolder.objects.create(user=user, name="Root")
        child = PersonalFolder.objects.create(user=user, name="Child", parent=root)
        PersonalResource.objects.create(
            user=user,
            folder=child,
            title="File",
            file=SimpleUploadedFile("child.pdf", b"%PDF-1.4 child"),
        )

        tree_response = authenticated_client.get("/api/personal-folders/tree/")
        assert tree_response.status_code == status.HTTP_200_OK
        assert any(item["id"] == str(root.id) for item in tree_response.data)

        contents_response = authenticated_client.get(f"/api/personal-folders/{child.id}/contents/")
        assert contents_response.status_code == status.HTTP_200_OK
        assert len(contents_response.data["breadcrumbs"]) >= 1
        assert len(contents_response.data["files"]) == 1

    def test_move_folder_validation_branches(self, authenticated_client, user):
        root = PersonalFolder.objects.create(user=user, name="Root")
        child = PersonalFolder.objects.create(user=user, name="Child", parent=root)
        duplicate_target = PersonalFolder.objects.create(user=user, name="Target")
        PersonalFolder.objects.create(user=user, name="Child", parent=duplicate_target)

        not_found = authenticated_client.post(
            f"/api/personal-folders/{child.id}/move/",
            {"parent_id": str(uuid4())},
            format="json",
        )
        assert not_found.status_code == status.HTTP_404_NOT_FOUND

        self_move = authenticated_client.post(
            f"/api/personal-folders/{child.id}/move/",
            {"parent_id": str(child.id)},
            format="json",
        )
        assert self_move.status_code == status.HTTP_400_BAD_REQUEST

        circular = authenticated_client.post(
            f"/api/personal-folders/{root.id}/move/",
            {"parent_id": str(child.id)},
            format="json",
        )
        assert circular.status_code == status.HTTP_400_BAD_REQUEST

        duplicate_name = authenticated_client.post(
            f"/api/personal-folders/{child.id}/move/",
            {"parent_id": str(duplicate_target.id)},
            format="json",
        )
        assert duplicate_name.status_code == status.HTTP_400_BAD_REQUEST

        to_root = authenticated_client.post(
            f"/api/personal-folders/{child.id}/move/",
            {"parent_id": None},
            format="json",
        )
        assert to_root.status_code == status.HTTP_200_OK
        child.refresh_from_db()
        assert child.parent is None


@pytest.mark.django_db
class TestPersonalResourceViewSetActions:
    """Cover personal resource retrieve/favorite/recent/storage/move/duplicate."""

    def test_retrieve_tracks_last_accessed(
        self, authenticated_client, personal_resource
    ):
        url = f"/api/personal-resources/{personal_resource.id}/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        personal_resource.refresh_from_db()
        assert personal_resource.last_accessed_at is not None

    def test_favorite_favorites_recent_and_storage(
        self, authenticated_client, personal_resource, user
    ):
        toggle = authenticated_client.post(
            f"/api/personal-resources/{personal_resource.id}/favorite/"
        )
        assert toggle.status_code == status.HTTP_200_OK
        assert toggle.data["is_favorite"] is True

        favorites = authenticated_client.get("/api/personal-resources/favorites/")
        assert favorites.status_code == status.HTTP_200_OK
        assert len(favorites.data) == 1

        personal_resource.mark_accessed()
        recent = authenticated_client.get("/api/personal-resources/recent/")
        assert recent.status_code == status.HTTP_200_OK
        assert len(recent.data) >= 1

        storage, _ = UserStorage.objects.get_or_create(user=user)
        storage.used_storage = 1024
        storage.save(update_fields=["used_storage"])
        storage_response = authenticated_client.get("/api/personal-resources/storage/")
        assert storage_response.status_code == status.HTTP_200_OK
        assert storage_response.data["used_storage"] == 1024

    def test_move_and_duplicate_personal_resource(
        self, authenticated_client, user, personal_resource
    ):
        target_folder = PersonalFolder.objects.create(user=user, name="Target")

        missing_folder = authenticated_client.post(
            f"/api/personal-resources/{personal_resource.id}/move/",
            {"folder_id": str(uuid4())},
            format="json",
        )
        assert missing_folder.status_code == status.HTTP_404_NOT_FOUND

        move_to_folder = authenticated_client.post(
            f"/api/personal-resources/{personal_resource.id}/move/",
            {"folder_id": str(target_folder.id)},
            format="json",
        )
        assert move_to_folder.status_code == status.HTTP_200_OK

        move_to_root = authenticated_client.post(
            f"/api/personal-resources/{personal_resource.id}/move/",
            {"folder_id": None},
            format="json",
        )
        assert move_to_root.status_code == status.HTTP_200_OK

        duplicate = authenticated_client.post(
            f"/api/personal-resources/{personal_resource.id}/duplicate/"
        )
        assert duplicate.status_code == status.HTTP_201_CREATED
        assert duplicate.data["title"].endswith("(Copy)")
        assert duplicate.data["source_type"] == "imported"


@pytest.mark.django_db
class TestResourceAuxiliaryEndpoints:
    """Cover additional ResourceViewSet and library dashboard branches."""

    def test_auxiliary_resource_actions_and_dashboard(
        self, public_resource, user, admin_user
    ):
        student_client = APIClient()
        student_client.force_authenticate(user=user)
        elevated_client = APIClient()
        elevated_client.force_authenticate(user=admin_user)

        unauthenticated_client = APIClient()
        unauth_uploads = unauthenticated_client.get("/api/resources/my_uploads/")
        assert unauth_uploads.status_code == status.HTTP_401_UNAUTHORIZED

        unauth_storage = unauthenticated_client.get("/api/resources/storage/")
        assert unauth_storage.status_code == status.HTTP_401_UNAUTHORIZED

        auth_storage = student_client.get("/api/resources/storage/")
        assert auth_storage.status_code == status.HTTP_200_OK
        assert "usage_percentage" in auth_storage.data

        denied_bulk = student_client.post(
            "/api/resources/bulk_action/",
            {"resource_ids": [str(public_resource.id)], "action": "pin"},
            format="json",
        )
        assert denied_bulk.status_code == status.HTTP_403_FORBIDDEN

        pin = elevated_client.post(
            "/api/resources/bulk_action/",
            {"resource_ids": [str(public_resource.id)], "action": "pin"},
            format="json",
        )
        assert pin.status_code == status.HTTP_200_OK
        public_resource.refresh_from_db()
        assert public_resource.is_pinned is True

        pinned = student_client.get("/api/resources/pinned/")
        assert pinned.status_code == status.HTTP_200_OK
        assert pinned.data["count"] >= 1

        public_resource.is_pinned = False
        public_resource.save(update_fields=["is_pinned"])
        dashboard = student_client.get(reverse("resources:library-dashboard"))
        assert dashboard.status_code == status.HTTP_200_OK
        assert "storage" in dashboard.data
        assert "stats" in dashboard.data
