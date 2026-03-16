"""Tests for favorites module."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.favorites.models import Favorite, FavoriteType
from apps.favorites.services import FavoriteService
from apps.resources.models import PersonalFolder, PersonalResource, Resource

User = get_user_model()


@pytest.fixture
def favorite_resource(db, admin_user):
    """Create an approved resource that can be favorited."""
    return Resource.objects.create(
        title="Favorite Target",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def private_resource(db, admin_user):
    return Resource.objects.create(
        title="Private Favorite Target",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=False,
    )


@pytest.fixture
def pending_resource(db, admin_user):
    return Resource.objects.create(
        title="Pending Favorite Target",
        resource_type="notes",
        uploaded_by=admin_user,
        status="pending",
        is_public=True,
    )


@pytest.fixture
def personal_folder(db, user):
    """Create a personal folder for the user."""
    return PersonalFolder.objects.create(user=user, name="Semester 1")


@pytest.fixture
def personal_file(db, user, personal_folder):
    """Create a personal file for favorite toggle tests."""
    return PersonalResource.objects.create(
        user=user,
        folder=personal_folder,
        title="My Private Notes",
        file=SimpleUploadedFile("private-notes.pdf", b"pdf-content"),
        visibility="private",
    )


@pytest.mark.django_db
class TestFavoritesModule:
    """Favorites endpoints and automations."""

    def test_resource_toggle_adds_and_removes_favorite(
        self, authenticated_client, user, favorite_resource
    ):
        url = f"/api/favorites/resources/{favorite_resource.id}/favorite/"
        add_response = authenticated_client.post(url, {}, format="json")
        assert add_response.status_code == status.HTTP_200_OK
        assert add_response.data["is_favorited"] is True
        assert Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        ).exists()

        remove_response = authenticated_client.post(url, {}, format="json")
        assert remove_response.status_code == status.HTTP_200_OK
        assert remove_response.data["is_favorited"] is False
        assert not Favorite.objects.filter(
            user=user, resource=favorite_resource
        ).exists()

    def test_create_endpoint_blocks_duplicates(
        self, authenticated_client, favorite_resource
    ):
        payload = {
            "favorite_type": FavoriteType.RESOURCE,
            "resource_id": str(favorite_resource.id),
        }
        first = authenticated_client.post(
            "/api/favorites/create/",
            payload,
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED

        second = authenticated_client.post(
            "/api/favorites/create/", payload, format="json"
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_shows_only_current_user_favorites(
        self, authenticated_client, user, favorite_resource
    ):
        other_user = User.objects.create_user(
            email="other-favorites@test.com",
            password="testpass123",
            full_name="Other User",
            registration_number="OTHF001",
            role="student",
        )
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        Favorite.objects.create(
            user=other_user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )

        response = authenticated_client.get(reverse("favorites:favorite-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_stats_endpoint_returns_counts(
        self,
        authenticated_client,
        user,
        favorite_resource,
        personal_folder,
        personal_file,
    ):
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        )
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        )

        response = authenticated_client.get("/api/favorites/stats/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_favorites"] == 3
        assert response.data["resource_count"] == 1
        assert response.data["folder_count"] == 1
        assert response.data["personal_file_count"] == 1

    def test_personal_file_toggle_syncs_is_favorite_flag(
        self, authenticated_client, personal_file
    ):
        url = f"/api/favorites/library/files/{personal_file.id}/favorite/"
        add_response = authenticated_client.post(url, {}, format="json")
        assert add_response.status_code == status.HTTP_200_OK
        personal_file.refresh_from_db()
        assert personal_file.is_favorite is True

        remove_response = authenticated_client.post(url, {}, format="json")
        assert remove_response.status_code == status.HTTP_200_OK
        personal_file.refresh_from_db()
        assert personal_file.is_favorite is False

    def test_create_endpoint_supports_personal_file_and_folder(
        self, authenticated_client, user, personal_file, personal_folder
    ):
        file_payload = {
            "favorite_type": FavoriteType.PERSONAL_FILE,
            "personal_file_id": str(personal_file.id),
        }
        folder_payload = {
            "favorite_type": FavoriteType.FOLDER,
            "personal_folder_id": str(personal_folder.id),
        }

        file_response = authenticated_client.post(
            "/api/favorites/create/", file_payload, format="json"
        )
        assert file_response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        ).exists()

        folder_response = authenticated_client.post(
            "/api/favorites/create/", folder_payload, format="json"
        )
        assert folder_response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        ).exists()

    def test_toggle_endpoint_validates_target(self, authenticated_client):
        response = authenticated_client.post("/api/favorites/toggle/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Exactly one" in str(response.data)

    def test_toggle_endpoint_supports_personal_targets(
        self, authenticated_client, user, personal_file, personal_folder
    ):
        file_add = authenticated_client.post(
            "/api/favorites/toggle/",
            {"personal_file_id": str(personal_file.id)},
            format="json",
        )
        assert file_add.status_code == status.HTTP_200_OK
        assert file_add.data["is_favorited"] is True
        assert Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        ).exists()

        folder_add = authenticated_client.post(
            "/api/favorites/toggle/",
            {"personal_folder_id": str(personal_folder.id)},
            format="json",
        )
        assert folder_add.status_code == status.HTTP_200_OK
        assert folder_add.data["is_favorited"] is True
        assert Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        ).exists()

    def test_folder_toggle_endpoint_syncs_folder_favorite_flag(
        self, authenticated_client, personal_folder
    ):
        url = f"/api/favorites/library/folders/{personal_folder.id}/favorite/"
        add_response = authenticated_client.post(url, {}, format="json")
        assert add_response.status_code == status.HTTP_200_OK
        personal_folder.refresh_from_db()
        assert personal_folder.is_favorite is True

        remove_response = authenticated_client.post(url, {}, format="json")
        assert remove_response.status_code == status.HTTP_200_OK
        personal_folder.refresh_from_db()
        assert personal_folder.is_favorite is False

    def test_delete_endpoint_is_owner_scoped(
        self, authenticated_client, user, favorite_resource
    ):
        favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        delete_response = authenticated_client.delete(f"/api/favorites/{favorite.id}/")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        other_user = User.objects.create_user(
            email="different-owner@test.com",
            password="testpass123",
            full_name="Different Owner",
            registration_number="OTHF002",
            role="student",
        )
        protected_favorite = Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        forbidden_delete = other_client.delete(f"/api/favorites/{protected_favorite.id}/")
        assert forbidden_delete.status_code == status.HTTP_404_NOT_FOUND

    def test_service_remove_and_is_favorited_helpers(
        self, user, favorite_resource, personal_file, personal_folder
    ):
        FavoriteService.add_favorite(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        FavoriteService.add_favorite(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        )
        FavoriteService.add_favorite(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        )

        assert FavoriteService.is_favorited(user=user, resource=favorite_resource)
        assert FavoriteService.is_favorited(user=user, personal_file=personal_file)
        assert FavoriteService.is_favorited(user=user, personal_folder=personal_folder)

        assert FavoriteService.remove_favorite(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        assert FavoriteService.remove_favorite(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        )
        assert FavoriteService.remove_favorite(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        )
        assert FavoriteService.remove_favorite(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        ) is False

    def test_unauthenticated_user_cannot_toggle_favorite(
        self, api_client, favorite_resource
    ):
        response = api_client.post(
            f"/api/favorites/resources/{favorite_resource.id}/favorite/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_private_or_pending_resource_cannot_be_favorited(
        self, authenticated_client, private_resource, pending_resource
    ):
        private_create = authenticated_client.post(
            "/api/favorites/create/",
            {
                "favorite_type": FavoriteType.RESOURCE,
                "resource_id": str(private_resource.id),
            },
            format="json",
        )
        assert private_create.status_code == status.HTTP_400_BAD_REQUEST

        pending_toggle = authenticated_client.post(
            "/api/favorites/toggle/",
            {"resource_id": str(pending_resource.id)},
            format="json",
        )
        assert pending_toggle.status_code == status.HTTP_400_BAD_REQUEST

    def test_favorites_list_can_be_filtered_by_type(
        self, authenticated_client, user, favorite_resource, personal_file, personal_folder
    ):
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=favorite_resource,
        )
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        )
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.FOLDER,
            personal_folder=personal_folder,
        )

        only_resources = authenticated_client.get("/api/favorites/?type=resources")
        assert only_resources.status_code == status.HTTP_200_OK
        assert only_resources.data["count"] == 1

        only_files = authenticated_client.get("/api/favorites/?type=files")
        assert only_files.status_code == status.HTTP_200_OK
        assert only_files.data["count"] == 1
