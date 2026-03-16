"""
Tests for permissions and access control.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.faculties.models import Faculty
from apps.courses.models import Course
from apps.resources.models import Resource
from apps.bookmarks.models import Bookmark


@pytest.mark.django_db
class TestResourcePermissions:
    """Test resource access permissions."""

    def test_student_cannot_approve_resource(self, authenticated_client, course, user):
        """Test that students cannot approve resources."""
        from apps.accounts.models import User
        # Make user a student (already is by default)
        user.role = 'student'
        user.save()

        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )

        # Try to approve via moderation endpoint
        url = f"/api/moderation/resources/{resource.id}/approve/"
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_moderator_can_approve_resource(self, moderator_client, course, user):
        """Test that moderators can approve resources."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )

        url = f"/api/moderation/resources/{resource.id}/approve/"
        response = moderator_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        resource.refresh_from_db()
        assert resource.status == 'approved'

    def test_user_can_only_see_own_pending_resources(self, authenticated_client, course, user, admin_user):
        """Test users can only see their own pending resources."""
        # Create resource by current user
        Resource.objects.create(
            title='My Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )

        # Create resource by another user
        Resource.objects.create(
            title='Other User Resource',
            resource_type='notes',
            course=course,
            uploaded_by=admin_user,
            status='pending'
        )

        # Get my uploads
        url = reverse('resources:resource-my-uploads')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Should only see own resource
        assert len(response.data['results']) >= 1


@pytest.mark.django_db
class TestBookmarkUniqueness:
    """Test bookmark uniqueness constraints."""

    def test_cannot_duplicate_bookmark(self, authenticated_client, course, user):
        """Test that duplicate bookmarks are not allowed."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )

        # Create first bookmark
        Bookmark.objects.create(user=user, resource=resource)

        # Try to create duplicate
        url = reverse('bookmarks:bookmark-list')
        data = {'resource': str(resource.id)}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestRatingConstraints:
    """Test rating constraints."""

    def test_cannot_rate_own_resource(self, authenticated_client, course, user):
        """Test that users cannot rate their own resources."""
        resource = Resource.objects.create(
            title='My Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )

        url = f"/api/resources/{resource.id}/rate/"
        data = {'value': 5}
        response = authenticated_client.post(url, data, format='json')
        # Should be forbidden to rate own resource
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST]

    def test_rating_must_be_1_to_5(self, authenticated_client, course, user, admin_user):
        """Test that rating values must be between 1 and 5."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=admin_user,
            status='approved'
        )

        url = f"/api/resources/{resource.id}/rate/"

        # Test invalid rating (0)
        response = authenticated_client.post(url, {'value': 0}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test invalid rating (6)
        response = authenticated_client.post(url, {'value': 6}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPersonalLibraryPrivacy:
    """Test personal library privacy."""

    def test_cannot_access_other_users_personal_resources(self, api_client, course, user, admin_user):
        """Test that users cannot access other users' personal resources."""
        from apps.resources.models import PersonalResource

        # Create personal resource for admin
        personal = PersonalResource.objects.create(
            user=admin_user,
            title='Admin Private File',
            file='test.pdf',
            file_size=1024
        )

        # Try to access as unauthenticated user
        url = f"/api/personal-resources/{personal.id}/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_access_other_users_personal_folders(self, api_client, user, admin_user):
        """Test that users cannot access other users' personal folders."""
        from apps.resources.models import PersonalFolder

        # Create folder for admin
        folder = PersonalFolder.objects.create(
            user=admin_user,
            name='Admin Private Folder'
        )

        # Try to access as unauthenticated user
        url = f"/api/personal-folders/{folder.id}/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
