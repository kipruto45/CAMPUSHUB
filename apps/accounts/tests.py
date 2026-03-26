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
from apps.accounts.constants import (
    EMAIL_NOT_VERIFIED_CODE,
    EMAIL_NOT_VERIFIED_MESSAGE,
)
from apps.payments.models import Subscription
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
class TestRegistrationAndVerification:
    def test_registration_requires_email_verification(
        self, api_client, settings, mailoutbox
    ):
        url = reverse("accounts:register")
        response = api_client.post(
            url,
            {
                "email": "new-user@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "full_name": "New User",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["requires_email_verification"] is True
        assert response.data["access"] is None
        assert response.data["refresh"] is None
        assert len(mailoutbox) == 1
        assert "Please verify your email" in mailoutbox[0].subject

    def test_login_blocks_unverified_user(self, api_client, test_user):
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {"email": test_user.email, "password": "SecurePass123!"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == EMAIL_NOT_VERIFIED_CODE
        assert response.data["detail"] == EMAIL_NOT_VERIFIED_MESSAGE

    def test_verified_web_login_auto_starts_student_trial(self, api_client, test_user):
        test_user.is_verified = True
        test_user.save(update_fields=["is_verified", "updated_at"])

        response = api_client.post(
            reverse("accounts:login"),
            {"email": test_user.email, "password": "SecurePass123!"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription = Subscription.objects.get(user=test_user, status="trialing")
        assert subscription.plan.tier == "basic"
        assert subscription.metadata.get("trial") is True
        assert subscription.metadata.get("trial_duration_days") == 7

    def test_resend_verification_uses_verification_email_template(
        self, api_client, test_user, mailoutbox
    ):
        url = reverse("accounts:resend_verify_email")
        response = api_client.post(
            url,
            {"email": test_user.email},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == "Verify Your Email Address"
        assert "Verify Your Email Address" in mailoutbox[0].alternatives[0][0]

    def test_mobile_login_blocks_unverified_user(self, api_client, test_user):
        response = api_client.post(
            "/api/mobile/login/",
            {"email": test_user.email, "password": "SecurePass123!"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == EMAIL_NOT_VERIFIED_CODE
        assert response.data["detail"] == EMAIL_NOT_VERIFIED_MESSAGE

    def test_verified_mobile_login_auto_starts_student_trial(self, api_client, test_user):
        test_user.is_verified = True
        test_user.save(update_fields=["is_verified", "updated_at"])

        response = api_client.post(
            "/api/mobile/login/",
            {"email": test_user.email, "password": "SecurePass123!"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription = Subscription.objects.get(user=test_user, status="trialing")
        assert subscription.plan.tier == "basic"
        assert subscription.metadata.get("trial") is True
        assert subscription.metadata.get("trial_duration_days") == 7

    def test_passkey_auth_blocks_unverified_user(self, api_client, monkeypatch):
        monkeypatch.setattr(
            "apps.accounts.views.PasswordlessAuthService.verify_passkey_authentication",
            lambda credential_data: {
                "success": False,
                "message": EMAIL_NOT_VERIFIED_MESSAGE,
                "code": EMAIL_NOT_VERIFIED_CODE,
            },
        )

        response = api_client.post(
            reverse("accounts:passkey-auth-complete"),
            {"credential": {"credentialId": "test-passkey"}},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == EMAIL_NOT_VERIFIED_CODE
        assert response.data["detail"] == EMAIL_NOT_VERIFIED_MESSAGE


@pytest.mark.django_db
class TestPasswordResetRequest:
    """Tests for the password reset request endpoint."""

    def test_password_reset_request_with_valid_email(
        self, api_client, test_user, settings, mailoutbox
    ):
        """Test that password reset request succeeds with valid email."""
        url = reverse("accounts:password_reset_request")
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
        url = reverse("accounts:password_reset_request")
        response = api_client.post(
            url, {"email": "nonexistent@example.com"}, format="json"
        )

        # Should return success to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK

    def test_password_reset_request_invalid_email_format(self, api_client, db):
        """Test that password reset request rejects invalid email format."""
        url = reverse("accounts:password_reset_request")
        response = api_client.post(
            url, {"email": "invalid-email"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_request_empty_email(self, api_client, db):
        """Test that password reset request rejects empty email."""
        url = reverse("accounts:password_reset_request")
        response = api_client.post(url, {"email": ""}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordResetConfirm:
    """Tests for the password reset confirmation endpoint."""

    def test_password_reset_confirm_success(self, api_client, test_user):
        """Test that password reset confirmation succeeds with valid token."""
        token = generate_signed_password_reset_token(test_user)
        url = reverse(
            "accounts:password_reset_confirm_token", kwargs={"token": token}
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
            "accounts:password_reset_confirm_token", kwargs={"token": token}
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
            "accounts:password_reset_confirm_token",
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
            "accounts:password_reset_confirm_token", kwargs={"token": token}
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
    def test_magic_link_request_returns_backend_consume_url_when_frontend_missing(
        self,
        api_client,
        test_user,
        mailoutbox,
        settings,
    ):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""

        url = reverse("accounts:magic-link-request")
        resp = api_client.post(url, {"email": test_user.email})
        assert resp.status_code == status.HTTP_200_OK
        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == "Your CampusHub Magic Link"
        assert "/api/auth/magic-link/consume/?token=" in mailoutbox[0].body

    def test_magic_link_request_prefers_frontend_magic_link_route(
        self,
        api_client,
        test_user,
        mailoutbox,
        settings,
    ):
        settings.FRONTEND_BASE_URL = "https://app.campushub.example"
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""

        url = reverse("accounts:magic-link-request")
        resp = api_client.post(url, {"email": test_user.email})

        assert resp.status_code == status.HTTP_200_OK
        assert len(mailoutbox) == 1
        assert "https://app.campushub.example/magic-link?token=" in mailoutbox[0].body

    def test_magic_link_consume_screen_renders(self, api_client):
        url = reverse("accounts:magic-link-consume")
        resp = api_client.get(url, {"token": "screen-token"})

        assert resp.status_code == status.HTTP_200_OK
        content = resp.content.decode()
        assert "One-tap sign in" in content
        assert "screen-token" in content

    def test_magic_link_consume_returns_tokens(self, api_client, test_user):
        test_user.is_verified = True
        test_user.save(update_fields=["is_verified", "updated_at"])
        token = generate_magic_link_token(test_user.id, ttl_minutes=5)
        url = reverse("accounts:magic-link-consume")
        resp = api_client.post(url, {"token": token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data and "refresh" in resp.data

    def test_magic_link_can_only_be_used_once(self, api_client, test_user):
        test_user.is_verified = True
        test_user.save(update_fields=["is_verified", "updated_at"])
        token = generate_magic_link_token(test_user.id, ttl_minutes=5)
        url = reverse("accounts:magic-link-consume")

        first = api_client.post(url, {"token": token})
        second = api_client.post(url, {"token": token})

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been used" in second.data["detail"].lower()

    def test_magic_link_consume_blocks_unverified_user(self, api_client, test_user):
        token = generate_magic_link_token(test_user.id, ttl_minutes=5)
        url = reverse("accounts:magic-link-consume")
        resp = api_client.post(url, {"token": token})

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data["code"] == EMAIL_NOT_VERIFIED_CODE
        assert resp.data["detail"] == EMAIL_NOT_VERIFIED_MESSAGE
        assert resp.data["email"] == test_user.email

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
