"""
Tests for password reset functionality.
"""
from datetime import date

import pytest
from django.core.cache import cache
from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import generate_magic_link_token
from apps.core.encryption import EncryptionService
from apps.two_factor.models import TwoFactorSetting
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


@pytest.mark.django_db
class TestMagicLink:
    def test_magic_link_request_returns_200(self, api_client, test_user):
        url = reverse("accounts:magic-link-request")
        resp = api_client.post(url, {"email": test_user.email})
        assert resp.status_code == status.HTTP_200_OK

    def test_magic_link_consume_returns_tokens(self, api_client, test_user):
        token = generate_magic_link_token(test_user.id, ttl_minutes=5)
        url = reverse("accounts:magic-link-consume")
        resp = api_client.post(url, {"token": token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data and "refresh" in resp.data

    def test_magic_link_can_only_be_used_once(self, api_client, test_user):
        token = generate_magic_link_token(test_user.id, ttl_minutes=5)
        url = reverse("accounts:magic-link-consume")

        first = api_client.post(url, {"token": token})
        second = api_client.post(url, {"token": token})

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been used" in second.data["detail"].lower()

    def test_magic_link_request_is_rate_limited(self, api_client, test_user):
        cache.clear()
        url = reverse("accounts:magic-link-request")

        for _ in range(5):
            resp = api_client.post(url, {"email": test_user.email})
            assert resp.status_code == status.HTTP_200_OK

        limited = api_client.post(url, {"email": test_user.email})
        assert limited.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestSensitiveFieldEncryption:
    @pytest.fixture(autouse=True)
    def _configure_encryption(self, settings):
        settings.ENCRYPTION_ENABLED = True
        settings.ENCRYPTION_ALLOW_FALLBACK = False
        settings.ENCRYPTION_MASTER_KEY = "1" * 64
        settings.ENCRYPTION_KEY_SALT = "test-encryption-salt"
        settings.ENCRYPTION_KEY_VERSION = 1
        settings.ENCRYPTION_PREVIOUS_KEYS = ""
        EncryptionService.clear_cache()
        cache.clear()

    def test_user_sensitive_fields_are_encrypted_at_rest(self, db):
        user = User.objects.create_user(
            email="encrypted@example.com",
            password="SecurePass123!",
            phone_number="+254700000001",
            student_id="STU-001",
            bio="Private user bio",
        )
        user.date_of_birth = date(2000, 1, 15)
        user.save()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT phone_number, student_id, bio, date_of_birth
                FROM accounts_user
                WHERE id = %s
                """,
                [user.id],
            )
            phone_value, student_id_value, bio_value, dob_value = cursor.fetchone()

        assert phone_value != "+254700000001"
        assert student_id_value != "STU-001"
        assert bio_value != "Private user bio"
        assert dob_value != "2000-01-15"
        assert EncryptionService.is_encrypted(phone_value)
        assert EncryptionService.is_encrypted(student_id_value)
        assert EncryptionService.is_encrypted(bio_value)
        assert EncryptionService.is_encrypted(dob_value)

    def test_two_factor_secrets_are_encrypted_at_rest(self, test_user):
        setting = TwoFactorSetting.objects.create(user=test_user)
        setting.generate_totp_secret()
        setting.generate_backup_codes()
        setting.save()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT totp_secret, backup_codes
                FROM two_factor_twofactorsetting
                WHERE user_id = %s
                """,
                [test_user.id],
            )
            totp_secret_value, backup_codes_value = cursor.fetchone()

        assert EncryptionService.is_encrypted(totp_secret_value)
        assert EncryptionService.is_encrypted(backup_codes_value)
        assert setting.verify_totp(
            __import__("pyotp").TOTP(setting.totp_secret).now()
        )

    def test_existing_encrypted_data_can_still_be_read_when_encryption_is_disabled(self, settings):
        encrypted = EncryptionService.encrypt("hello world", context="tests.sample")
        settings.ENCRYPTION_ENABLED = False
        EncryptionService.clear_cache()

        assert EncryptionService.decrypt(encrypted, context="tests.sample") == "hello world"
