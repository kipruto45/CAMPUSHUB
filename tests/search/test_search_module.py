"""Tests for search module endpoints and automations."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from apps.resources.models import PersonalResource, Resource
from apps.search.models import RecentSearch


@pytest.fixture
def searchable_resource(db, admin_user):
    """Create an approved public resource for search tests."""
    return Resource.objects.create(
        title="Data Structures Notes",
        description="Stacks, queues, and trees tutorial",
        tags="data-structures,algorithms,trees",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def non_public_search_resource(db, admin_user):
    """Create resources that should not appear in search results."""
    Resource.objects.create(
        title="Hidden Pending Resource",
        description="Should never appear",
        tags="hidden",
        resource_type="notes",
        uploaded_by=admin_user,
        status="pending",
        is_public=True,
    )
    Resource.objects.create(
        title="Hidden Private Resource",
        description="Should never appear",
        tags="private",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=False,
    )


@pytest.fixture
def personal_search_file(db, user):
    """Create a personal file searchable in personal search endpoint."""
    return PersonalResource.objects.create(
        user=user,
        title="Private Algorithms File",
        description="My class summary",
        tags="algorithms,notes",
        file=SimpleUploadedFile("private-algo.pdf", b"pdf-bytes"),
        visibility="private",
    )


@pytest.mark.django_db
class TestSearchModule:
    """Search list, suggestions, recent history, and personal search tests."""

    def test_authenticated_search_saves_recent_search(
        self, authenticated_client, user, searchable_resource
    ):
        response = authenticated_client.get(
            f"{reverse('search:search')}?q=data"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 1
        assert RecentSearch.objects.filter(
            user=user,
            normalized_query="data",
        ).exists()

    def test_recent_searches_requires_authentication(self, api_client):
        response = api_client.get(reverse("search:search-recent"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_recent_searches_returns_latest_first(
        self, authenticated_client, user, searchable_resource
    ):
        authenticated_client.get(f"{reverse('search:search')}?q=trees")
        authenticated_client.get(f"{reverse('search:search')}?q=queues")

        response = authenticated_client.get(reverse("search:search-recent"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["recent_searches"]) >= 2
        assert response.data["recent_searches"][0]["normalized_query"] in {
            "queues",
            "trees",
        }

    def test_recent_searches_can_be_cleared(self, authenticated_client, user):
        RecentSearch.objects.create(
            user=user,
            query="algorithms",
            normalized_query="algorithms",
            results_count=3,
            filters={},
        )
        RecentSearch.objects.create(
            user=user,
            query="data",
            normalized_query="data",
            results_count=4,
            filters={},
        )

        response = authenticated_client.delete(reverse("search:search-recent"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Recent searches cleared."
        assert response.data["deleted_count"] == 2
        assert not RecentSearch.objects.filter(user=user).exists()

    def test_search_suggestions_returns_matches(
        self, api_client, searchable_resource
    ):
        response = api_client.get(
            f"{reverse('search:search-suggestions')}?q=data"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "suggestions" in response.data
        assert any(
            "Data Structures Notes" == item
            for item in response.data["suggestions"]
        )

    def test_personal_search_returns_user_files(
        self, authenticated_client, personal_search_file
    ):
        response = authenticated_client.get(
            f"{reverse('search:search-personal')}?q=private"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert (
            response.data["results"][0]["id"] == str(personal_search_file.id)
        )

    def test_search_results_exclude_non_public_or_non_approved_resources(
        self, api_client, searchable_resource, non_public_search_resource
    ):
        response = api_client.get(f"{reverse('search:search')}?q=resource")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

        response = api_client.get(f"{reverse('search:search')}?q=data")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 1

    def test_search_supports_file_type_and_sort_filters(self, api_client, admin_user):
        old = Resource.objects.create(
            title="Old PDF Notes",
            description="Legacy notes",
            tags="legacy",
            resource_type="notes",
            file_type="pdf",
            view_count=5,
            uploaded_by=admin_user,
            status="approved",
            is_public=True,
        )
        new = Resource.objects.create(
            title="New PDF Notes",
            description="New notes",
            tags="new",
            resource_type="notes",
            file_type="pdf",
            view_count=20,
            uploaded_by=admin_user,
            status="approved",
            is_public=True,
        )

        response = api_client.get(
            f"{reverse('search:search')}?q=notes&file_type=pdf&sort=most_viewed"
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in response.data["results"]]
        assert str(new.id) in ids and str(old.id) in ids
        assert ids.index(str(new.id)) < ids.index(str(old.id))

    def test_recent_search_single_delete(self, authenticated_client, user):
        item = RecentSearch.objects.create(
            user=user,
            query="algorithms",
            normalized_query="algorithms",
            results_count=2,
            filters={},
        )
        second = RecentSearch.objects.create(
            user=user,
            query="structures",
            normalized_query="structures",
            results_count=3,
            filters={},
        )

        response = authenticated_client.delete(
            reverse("search:search-recent-delete", kwargs={"search_id": item.id})
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted_count"] == 1
        assert not RecentSearch.objects.filter(id=item.id).exists()
        assert RecentSearch.objects.filter(id=second.id).exists()
