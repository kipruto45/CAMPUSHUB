"""
Tests for password reset functionality.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.verification import (
    generate_signed_password_reset_token,
    validate_signed_password_reset_token,
)


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user for password reset tests."""
    user = User.objects.create_user(
        email="test@example.com",
        password="SecurePass123!",
        full_name="Test User",
    )
    return user


@pytest.mark.django_db
class TestPasswordResetRequest:
    """Tests for the password reset request endpoint."""

    def test_password_reset_request_with_valid_email(
        self, api_client, test_user, settings, mailoutbox
    ):
        """Test that password reset request succeeds with valid email."""
        url = reverse("password_reset_request")
        response = api_client.post(
            url, {"email": "test@example.com"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data["message"] == "Password reset email sent."
        )

    def test_password_reset_request_email_not_found(
        self, api_client, db, settings, mailoutbox
    ):
        """Test that password reset request works even for non-existent email (security)."""
        url = reverse("password_reset_request")
        response = api_client.post(
            url, {"email": "nonexistent@example.com"}, format="json"
        )

        # Should return success to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK

    def test_password_reset_request_invalid_email_format(self, api_client, db):
        """Test that password reset request rejects invalid email format."""
        url = reverse("password_reset_request")
        response = api_client.post(
            url, {"email": "invalid-email"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_request_empty_email(self, api_client, db):
        """Test that password reset request rejects empty email."""
        url = reverse("password_reset_request")
        response = api_client.post(url, {"email": ""}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordResetConfirm:
    """Tests for the password reset confirmation endpoint."""

    def test_password_reset_confirm_success(self, api_client, test_user):
        """Test that password reset confirmation succeeds with valid token."""
        token = generate_signed_password_reset_token(test_user)
        url = reverse(
            "password_reset_confirm_token", kwargs={"token": token}
        )
        response = api_client.post(
            url,
            {
                "new_password": "NewSecurePass456!",
                "new_password_confirm": "NewSecurePass456!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Password reset successful."

        # Verify the password was actually changed
        test_user.refresh_from_db()
        assert test_user.check_password("NewSecurePass456!")

    def test_password_reset_confirm_mismatched_passwords(
        self, api_client, test_user
    ):
        """Test that password reset confirmation rejects mismatched passwords."""
        token = generate_signed_password_reset_token(test_user)
        url = reverse(
            "password_reset_confirm_token", kwargs={"token": token}
        )
        response = api_client.post(
            url,
            {
                "new_password": "NewSecurePass456!",
                "new_password_confirm": "DifferentPass789!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_confirm_invalid_token(self, api_client, db):
        """Test that password reset confirmation rejects invalid token."""
        url = reverse(
            "password_reset_confirm_token",
            kwargs={"token": "invalid-token-12345"},
        )
        response = api_client.post(
            url,
            {
                "new_password": "NewSecurePass456!",
                "new_password_confirm": "NewSecurePass456!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_confirm_weak_password(self, api_client, test_user):
        """Test that password reset confirmation rejects weak passwords."""
        token = generate_signed_password_reset_token(test_user)
        url = reverse(
            "password_reset_confirm_token", kwargs={"token": token}
        )
        response = api_client.post(
            url,
            {"new_password": "weak", "new_password_confirm": "weak"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMobilePasswordReset:
    """Tests for the mobile password reset endpoints."""

    def test_mobile_password_reset_request(
        self, api_client, test_user, settings, mailoutbox
    ):
        """Test mobile password reset request endpoint."""
        url = "/api/mobile/password/reset/"
        response = api_client.post(url, {"email": "test@example.com"})

        assert response.status_code == status.HTTP_200_OK

    def test_mobile_password_reset_confirm(
        self, api_client, test_user, settings, mailoutbox
    ):
        """Test mobile password reset confirmation endpoint."""
        token = generate_signed_password_reset_token(test_user)
        url = f"/api/mobile/password/reset/confirm/{token}/"
        response = api_client.post(
            url,
            {
                "new_password": "NewSecurePass456!",
                "new_password_confirm": "NewSecurePass456!",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify the password was changed
        test_user.refresh_from_db()
        assert test_user.check_password("NewSecurePass456!")
