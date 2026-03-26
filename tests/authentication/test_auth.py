"""
Tests for authentication endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestAuthentication:
    """Test authentication endpoints."""

    def test_user_registration(self, api_client):
        """Test user registration."""
        url = reverse('accounts:register')
        data = {
            'email': 'newuser@test.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'full_name': 'New User',
            'registration_number': 'NEW001',
            'role': 'student'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['requires_email_verification'] is True
        assert response.data['access'] is None
        assert response.data['refresh'] is None

    def test_user_login(self, api_client, user):
        """Test user login."""
        user.is_verified = True
        user.save(update_fields=['is_verified'])

        url = reverse('accounts:login')
        data = {
            'email': 'student@test.com',
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_invalid_login(self, api_client, user):
        """Test login with invalid credentials."""
        url = reverse('accounts:login')
        data = {
            'email': 'student@test.com',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, user):
        """Test token refresh."""
        user.is_verified = True
        user.save(update_fields=['is_verified'])

        # First login to get refresh token
        login_url = reverse('accounts:login')
        login_data = {
            'email': 'student@test.com',
            'password': 'testpass123'
        }
        login_response = api_client.post(login_url, login_data, format='json')
        refresh_token = login_response.data.get('refresh')

        # Then refresh
        refresh_url = reverse('accounts:token_refresh')
        refresh_data = {'refresh': refresh_token}
        response = api_client.post(refresh_url, refresh_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data


@pytest.mark.django_db
class TestProfile:
    """Test profile endpoints."""

    def test_get_profile_authenticated(self, authenticated_client, user):
        """Test getting profile when authenticated."""
        url = reverse('accounts:profile')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email

    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile when not authenticated."""
        url = reverse('accounts:profile')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile(self, authenticated_client, user):
        """Test updating profile."""
        url = reverse('accounts:profile')
        data = {'full_name': 'Updated Name'}
        response = authenticated_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['full_name'] == 'Updated Name'
