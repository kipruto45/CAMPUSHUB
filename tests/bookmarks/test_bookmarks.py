"""Tests for bookmarks module."""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.resources.models import Resource
from apps.bookmarks.models import Bookmark
from apps.accounts.models import Profile, UserActivity


@pytest.fixture
def public_resource(db, user):
    """Create a bookmarkable public approved resource."""
    return Resource.objects.create(
        title='Public Notes',
        resource_type='notes',
        uploaded_by=user,
        status='approved',
        is_public=True,
    )


@pytest.fixture
def private_resource(db, admin_user):
    """Create a private approved resource."""
    return Resource.objects.create(
        title='Private Notes',
        resource_type='notes',
        uploaded_by=admin_user,
        status='approved',
        is_public=False,
    )


@pytest.fixture
def pending_resource(db, admin_user):
    """Create a non-approved resource."""
    return Resource.objects.create(
        title='Pending Notes',
        resource_type='notes',
        uploaded_by=admin_user,
        status='pending',
        is_public=True,
    )


@pytest.mark.django_db
class TestBookmarksModule:
    """Bookmark module functional and permission tests."""

    def test_user_can_bookmark_public_resource(self, authenticated_client, public_resource):
        response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(public_resource.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Bookmark.objects.filter(resource=public_resource).exists()

    def test_user_can_remove_bookmark(self, authenticated_client, user, public_resource):
        bookmark = Bookmark.objects.create(user=user, resource=public_resource)
        response = authenticated_client.delete(
            reverse('bookmarks:bookmark-detail', kwargs={'pk': bookmark.id})
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Bookmark.objects.filter(id=bookmark.id).exists()

    def test_bookmark_list_shows_only_own_items(self, authenticated_client, user, admin_user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        other_resource = Resource.objects.create(
            title='Other Public Notes',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
        )
        Bookmark.objects.create(user=admin_user, resource=other_resource)

        response = authenticated_client.get(reverse('bookmarks:bookmark-list'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    def test_duplicate_bookmark_blocked(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(public_resource.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_resource_id_rejected(self, authenticated_client):
        response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': '00000000-0000-0000-0000-000000000000'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_user_cannot_bookmark(self, api_client, public_resource):
        response = api_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(public_resource.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_cannot_remove_another_users_bookmark(self, authenticated_client, admin_user, public_resource):
        bookmark = Bookmark.objects.create(user=admin_user, resource=public_resource)
        response = authenticated_client.delete(
            reverse('bookmarks:bookmark-detail', kwargs={'pk': bookmark.id})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_private_resource_bookmark_blocked(self, authenticated_client, private_resource):
        response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(private_resource.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_pending_resource_bookmark_blocked(self, authenticated_client, pending_resource):
        response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(pending_resource.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_recent_bookmarks_returns_latest_first(self, authenticated_client, user, admin_user):
        first_resource = Resource.objects.create(
            title='First',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
        )
        second_resource = Resource.objects.create(
            title='Second',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
        )
        Bookmark.objects.create(user=user, resource=first_resource)
        second = Bookmark.objects.create(user=user, resource=second_resource)

        response = authenticated_client.get(reverse('bookmarks:bookmark-recent'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]['id'] == str(second.id)

    def test_resource_endpoints_show_saved_state(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)

        list_response = authenticated_client.get(reverse('resources:resource-list'))
        assert list_response.status_code == status.HTTP_200_OK
        list_item = next(item for item in list_response.data['results'] if item['id'] == str(public_resource.id))
        assert list_item['is_bookmarked'] is True

        detail_response = authenticated_client.get(f"/api/resources/{public_resource.slug}/")
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['is_bookmarked'] is True

    def test_bookmark_toggle_works_from_resource_endpoint_by_slug_and_id(self, authenticated_client, user, public_resource):
        slug_url = f"/api/resources/{public_resource.slug}/bookmark/"
        id_url = f"/api/resources/{public_resource.id}/bookmark/"

        create_response = authenticated_client.post(slug_url)
        assert create_response.status_code == status.HTTP_200_OK
        assert Bookmark.objects.filter(user=user, resource=public_resource).exists()

        remove_response = authenticated_client.delete(id_url)
        assert remove_response.status_code == status.HTTP_200_OK
        assert not Bookmark.objects.filter(user=user, resource=public_resource).exists()

    def test_bookmark_hidden_after_resource_unpublished(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        public_resource.status = 'rejected'
        public_resource.save(update_fields=['status'])

        response = authenticated_client.get(reverse('bookmarks:bookmark-list'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0

    def test_bookmark_count_endpoint(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        response = authenticated_client.get(reverse('bookmarks:bookmark-count'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    def test_bookmark_count_automation_updates_profile(self, authenticated_client, user, public_resource):
        create_response = authenticated_client.post(
            reverse('bookmarks:bookmark-list'),
            {'resource': str(public_resource.id)},
            format='json',
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.refresh_from_db()
        assert profile.total_bookmarks == 1

        bookmark = Bookmark.objects.get(user=user, resource=public_resource)
        delete_response = authenticated_client.delete(
            reverse('bookmarks:bookmark-detail', kwargs={'pk': bookmark.id})
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        profile.refresh_from_db()
        assert profile.total_bookmarks == 0

    def test_bookmark_deleted_when_resource_deleted(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        public_resource.delete()
        response = authenticated_client.get(reverse('bookmarks:bookmark-list'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0

    def test_model_level_bookmark_signals_update_profile_and_activity(self, user, public_resource):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.total_bookmarks = 0
        profile.save(update_fields=['total_bookmarks'])

        bookmark = Bookmark.objects.create(user=user, resource=public_resource)
        profile.refresh_from_db()
        assert profile.total_bookmarks == 1
        assert UserActivity.objects.filter(user=user, action='bookmark').exists()

        bookmark.delete()
        profile.refresh_from_db()
        assert profile.total_bookmarks == 0

    def test_dashboard_recent_bookmarks_excludes_unpublished_resources(self, authenticated_client, user, public_resource):
        Bookmark.objects.create(user=user, resource=public_resource)
        public_resource.status = 'rejected'
        public_resource.save(update_fields=['status'])

        response = authenticated_client.get(reverse('dashboard:dashboard-activity'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['recent_bookmarks'] == []
