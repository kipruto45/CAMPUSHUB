"""Tests for library and storage module."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from apps.library import services as library_services
from apps.resources.models import PersonalFolder, PersonalResource

User = get_user_model()


@pytest.fixture
def root_folder(db, user):
    """Create a root folder for the authenticated user."""
    return PersonalFolder.objects.create(user=user, name="My Library Root")


@pytest.fixture
def personal_file(db, user, root_folder):
    """Create a personal file for trash and restore tests."""
    return PersonalResource.objects.create(
        user=user,
        folder=root_folder,
        title="Algorithms Notes",
        file=SimpleUploadedFile("algorithms.pdf", b"pdf-bytes"),
        visibility="private",
    )


@pytest.mark.django_db
class TestLibraryModule:
    """Storage summary, trash lifecycle, and folder access tests."""

    def test_storage_summary_requires_authentication(self, api_client):
        response = api_client.get("/api/library/storage-summary/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_storage_summary_returns_expected_fields(
        self, authenticated_client
    ):
        response = authenticated_client.get("/api/library/storage-summary/")
        assert response.status_code == status.HTTP_200_OK
        assert "storage_limit_bytes" in response.data
        assert "storage_used_bytes" in response.data
        assert "storage_remaining_bytes" in response.data
        assert "usage_percent" in response.data
        assert "warning_level" in response.data

    def test_move_to_trash_and_restore_file(
        self, authenticated_client, personal_file
    ):
        move_response = authenticated_client.post(
            "/api/library/trash/move-to-trash/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert move_response.status_code == status.HTTP_200_OK

        personal_file.refresh_from_db()
        assert personal_file.is_deleted is True

        files_response = authenticated_client.get("/api/library/files/")
        assert files_response.status_code == status.HTTP_200_OK
        assert files_response.data["count"] == 0

        trash_response = authenticated_client.get("/api/library/trash/")
        assert trash_response.status_code == status.HTTP_200_OK
        assert len(trash_response.data) == 1

        restore_response = authenticated_client.post(
            "/api/library/trash/restore/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert restore_response.status_code == status.HTTP_200_OK
        personal_file.refresh_from_db()
        assert personal_file.is_deleted is False

    def test_permanent_delete_removes_trashed_file(
        self, authenticated_client, user, personal_file
    ):
        authenticated_client.post(
            "/api/library/trash/move-to-trash/",
            {"file_id": str(personal_file.id)},
            format="json",
        )

        delete_response = authenticated_client.post(
            "/api/library/trash/permanent-delete/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert delete_response.status_code == status.HTTP_200_OK
        assert not PersonalResource.all_objects.filter(
            id=personal_file.id, user=user
        ).exists()

    def test_folder_detail_uses_uuid_path_converter(
        self, authenticated_client, root_folder
    ):
        response = authenticated_client.get(
            f"/api/library/folders/{root_folder.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(root_folder.id)

    def test_move_restore_and_permanent_delete_not_found(self, authenticated_client):
        missing_uuid = "11111111-1111-1111-1111-111111111111"

        move_response = authenticated_client.post(
            "/api/library/trash/move-to-trash/",
            {"file_id": missing_uuid},
            format="json",
        )
        assert move_response.status_code == status.HTTP_404_NOT_FOUND

        restore_response = authenticated_client.post(
            "/api/library/trash/restore/",
            {"file_id": missing_uuid},
            format="json",
        )
        assert restore_response.status_code == status.HTTP_404_NOT_FOUND

        permanent_delete_response = authenticated_client.post(
            "/api/library/trash/permanent-delete/",
            {"file_id": missing_uuid},
            format="json",
        )
        assert permanent_delete_response.status_code == status.HTTP_404_NOT_FOUND

    def test_trash_endpoints_surface_service_errors(
        self, authenticated_client, personal_file, monkeypatch
    ):
        def permission_error(*args, **kwargs):
            raise PermissionError("not allowed")

        def value_error(*args, **kwargs):
            raise ValueError("bad state")

        monkeypatch.setattr("apps.library.views.move_file_to_trash", permission_error)
        move_response = authenticated_client.post(
            "/api/library/trash/move-to-trash/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert move_response.status_code == status.HTTP_403_FORBIDDEN

        personal_file.is_deleted = True
        personal_file.save(update_fields=["is_deleted"])

        monkeypatch.setattr("apps.library.views.restore_trashed_file", value_error)
        restore_response = authenticated_client.post(
            "/api/library/trash/restore/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert restore_response.status_code == status.HTTP_400_BAD_REQUEST

        monkeypatch.setattr("apps.library.views.permanently_delete_file", value_error)
        permanent_delete_response = authenticated_client.post(
            "/api/library/trash/permanent-delete/",
            {"file_id": str(personal_file.id)},
            format="json",
        )
        assert permanent_delete_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_folder_list_and_create_behaviour(self, authenticated_client, user):
        root = PersonalFolder.objects.create(user=user, name="Root A")
        PersonalFolder.objects.create(user=user, name="Child A", parent=root)

        list_response = authenticated_client.get("/api/library/folders/")
        assert list_response.status_code == status.HTTP_200_OK
        listed_names = {item["name"] for item in list_response.data["results"]}
        assert "Root A" in listed_names
        assert "Child A" not in listed_names

        create_response = authenticated_client.post(
            "/api/library/folders/",
            {"name": "Created Via API", "color": "#3b82f6"},
            format="json",
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        created = PersonalFolder.objects.get(id=create_response.data["id"])
        assert created.user == user

    def test_storage_and_file_validation_service_helpers(self, user, root_folder):
        first = PersonalResource.objects.create(
            user=user,
            folder=root_folder,
            title="File 1",
            file=SimpleUploadedFile("f1.pdf", b"12345"),
            visibility="private",
        )
        PersonalResource.objects.create(
            user=user,
            folder=root_folder,
            title="File 2",
            file=SimpleUploadedFile("f2.pdf", b"1234567"),
            visibility="private",
        )

        summary = library_services.get_storage_summary(user)
        assert summary["total_files"] == 2
        assert summary["storage_used_bytes"] >= first.file_size

        can_upload, error = library_services.can_user_upload_file(
            user, library_services.MAX_FILE_SIZE + 1
        )
        assert can_upload is False
        assert "exceeds maximum allowed size" in error

        assert library_services.is_allowed_file_type("notes.pdf") is True
        assert library_services.is_allowed_file_type("archive.exe") is False
        assert library_services.get_folder_storage(user, root_folder) >= first.file_size

    def test_trash_service_permission_and_state_checks(self, user, personal_file):
        other_user = User.objects.create_user(
            email="library-other@test.com",
            password="testpass123",
            full_name="Library Other",
            registration_number="LIB001",
            role="student",
        )

        with pytest.raises(PermissionError):
            library_services.move_file_to_trash(other_user, personal_file)

        library_services.move_file_to_trash(user, personal_file)
        personal_file.refresh_from_db()
        assert personal_file.is_deleted is True

        with pytest.raises(ValueError):
            library_services.move_file_to_trash(user, personal_file)

        with pytest.raises(PermissionError):
            library_services.restore_trashed_file(other_user, personal_file)

        restored = library_services.restore_trashed_file(user, personal_file)
        assert restored.is_deleted is False

        with pytest.raises(ValueError):
            library_services.restore_trashed_file(user, personal_file)

    def test_restore_to_root_when_original_folder_not_owned(self, user):
        owner_folder = PersonalFolder.objects.create(user=user, name="Owner Folder")
        other_user = User.objects.create_user(
            email="library-owner-mismatch@test.com",
            password="testpass123",
            full_name="Library Mismatch",
            registration_number="LIB002",
            role="student",
        )
        foreign_folder = PersonalFolder.objects.create(user=other_user, name="Foreign")

        file_obj = PersonalResource.objects.create(
            user=user,
            folder=owner_folder,
            title="Restoration Case",
            file=SimpleUploadedFile("restore.pdf", b"restore"),
            visibility="private",
        )
        file_obj.original_folder = foreign_folder
        file_obj.folder = None
        file_obj.is_deleted = True
        file_obj.save(update_fields=["original_folder", "folder", "is_deleted"])

        restored = library_services.restore_trashed_file(user, file_obj)
        assert restored.folder is None

    def test_permanent_delete_service_checks(self, user, personal_file):
        other_user = User.objects.create_user(
            email="library-delete-other@test.com",
            password="testpass123",
            full_name="Library Delete Other",
            registration_number="LIB003",
            role="student",
        )

        with pytest.raises(PermissionError):
            library_services.permanently_delete_file(other_user, personal_file)

        with pytest.raises(ValueError):
            library_services.permanently_delete_file(user, personal_file)

        library_services.move_file_to_trash(user, personal_file)
        assert library_services.permanently_delete_file(user, personal_file) is True
        assert not PersonalResource.all_objects.filter(id=personal_file.id).exists()

    def test_delete_folder_endpoint_is_owner_scoped(self, user, root_folder):
        other_user = User.objects.create_user(
            email="library-folder-owner@test.com",
            password="testpass123",
            full_name="Library Folder Owner",
            registration_number="LIB004",
            role="student",
        )
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        response = other_client.delete(f"/api/library/folders/{root_folder.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
