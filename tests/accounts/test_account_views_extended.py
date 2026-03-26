"""Extended tests for accounts views to cover auth and admin branches."""

from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import RequestFactory, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserActivity, UserPreference
from apps.accounts.verification import (generate_signed_password_reset_token,
                                        generate_signed_verification_token)


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _mark_user_verified(user):
    user.is_verified = True
    user.save(update_fields=["is_verified"])


@pytest.mark.django_db
def test_register_succeeds_even_when_verification_email_fails(api_client):
    with patch(
        "apps.accounts.views.EmailService.send_template_email",
        side_effect=RuntimeError("mail down"),
    ), patch(
        "apps.accounts.views.EmailService.send_email",
        side_effect=RuntimeError("mail down"),
    ):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "email": "extended-register@test.com",
                "password": "strongpass123",
                "password_confirm": "strongpass123",
                "full_name": "Extended Register",
                "registration_number": "EXT001",
            },
            format="json",
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(email="extended-register@test.com").exists()


@pytest.mark.django_db
def test_register_sends_welcome_verification_email(api_client):
    mail.outbox.clear()

    response = api_client.post(
        reverse("accounts:register"),
        {
            "email": "register-mail@test.com",
            "password": "strongpass123",
            "password_confirm": "strongpass123",
            "full_name": "Register Mail",
            "registration_number": "EXTMAIL001",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["register-mail@test.com"]
    assert "Welcome" in mail.outbox[0].subject


@pytest.mark.django_db
def test_login_lockout_kicks_in_after_repeated_invalid_payloads(api_client, user):
    url = reverse("accounts:login")
    cache.delete(f"auth:failed-login:{user.email}")

    for _ in range(5):
        response = api_client.post(url, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    locked = api_client.post(
        url, {"email": user.email, "password": "testpass123"}, format="json"
    )
    assert locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    cache.delete(f"auth:failed-login:{user.email}")


@pytest.mark.django_db
def test_login_triggers_suspicious_alert_when_detector_returns_true(api_client, user):
    _mark_user_verified(user)

    with patch("apps.accounts.views._is_suspicious_login", return_value=True), patch(
        "apps.accounts.views._send_suspicious_login_alert"
    ) as alert_mock:
        response = api_client.post(
            reverse("accounts:login"),
            {"email": user.email, "password": "testpass123"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert alert_mock.called is True


@pytest.mark.django_db
def test_is_suspicious_login_helper_detects_new_ip_and_agent(user):
    from apps.accounts.views import _is_suspicious_login

    factory = RequestFactory()

    # No identifiable request fingerprint => not suspicious.
    empty_request = factory.post("/api/auth/login/")
    assert _is_suspicious_login(user, empty_request) is False

    UserActivity.objects.create(
        user=user,
        action="login",
        ip_address="10.0.0.1",
        user_agent="UA-1",
        description="old login 1",
    )
    UserActivity.objects.create(
        user=user,
        action="login",
        ip_address="10.0.0.2",
        user_agent="UA-2",
        description="old login 2",
    )

    suspicious_request = factory.post(
        "/api/auth/login/",
        HTTP_USER_AGENT="UA-NEW",
        REMOTE_ADDR="10.0.0.99",
    )
    assert _is_suspicious_login(user, suspicious_request) is True


@pytest.mark.django_db
def test_send_suspicious_login_alert_creates_notification_and_respects_preferences(user):
    from apps.accounts.views import _send_suspicious_login_alert

    factory = RequestFactory()
    request = factory.post(
        "/api/auth/login/",
        HTTP_USER_AGENT="CampusHub Android",
        REMOTE_ADDR="127.0.0.9",
    )

    with patch(
        "apps.notifications.services.NotificationService.create_notification"
    ) as notify_mock, patch(
        "apps.accounts.views.EmailService.send_email"
    ) as send_mail_mock:
        _send_suspicious_login_alert(user, request)
        assert notify_mock.called is True
        assert send_mail_mock.called is True

    preferences, _ = UserPreference.objects.get_or_create(user=user)
    preferences.email_notifications = False
    preferences.save(update_fields=["email_notifications"])
    with patch("apps.accounts.views.EmailService.send_email") as send_mail_mock:
        _send_suspicious_login_alert(user, request)
        send_mail_mock.assert_not_called()


@pytest.mark.django_db
def test_logout_blacklists_refresh_token(user):
    client = _auth_client(user)
    refresh_token = RefreshToken.for_user(user)

    response = client.post(
        reverse("accounts:logout"), {"refresh": str(refresh_token)}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    assert BlacklistedToken.objects.filter(token__token=str(refresh_token)).exists()


@pytest.mark.django_db
def test_logout_blacklists_refresh_token_from_mobile_payload(user):
    client = _auth_client(user)
    refresh_token = RefreshToken.for_user(user)

    response = client.post(
        reverse("accounts:logout"),
        {"refresh_token": str(refresh_token)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert BlacklistedToken.objects.filter(token__token=str(refresh_token)).exists()


@pytest.mark.django_db
def test_logout_returns_success_even_on_internal_failure(user, monkeypatch):
    client = _auth_client(user)

    def raise_failure(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr("apps.accounts.views.OutstandingToken.objects.filter", raise_failure)
    response = client.post(reverse("accounts:logout"), {"refresh": "bad"}, format="json")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_login_parses_string_remember_me_flag(user, monkeypatch):
    _mark_user_verified(user)

    client = APIClient()
    captured = {}

    def fake_generate_tokens(user_obj, remember_me=False):
        captured["remember_me"] = remember_me
        return {"access": "access-token", "refresh": "refresh-token"}

    monkeypatch.setattr("apps.accounts.views.generate_tokens_for_user", fake_generate_tokens)

    false_response = client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "testpass123", "remember_me": "false"},
        format="json",
    )
    assert false_response.status_code == status.HTTP_200_OK
    assert false_response.data["remember_me"] is False
    assert captured["remember_me"] is False

    true_response = client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "testpass123", "remember_me": "true"},
        format="json",
    )
    assert true_response.status_code == status.HTTP_200_OK
    assert true_response.data["remember_me"] is True
    assert captured["remember_me"] is True


@pytest.mark.django_db
def test_password_reset_request_sends_email_for_active_user_and_skips_inactive(user):
    url = reverse("accounts:password_reset_request")

    with patch("apps.accounts.views.EmailService.send_template_email") as send_mail_mock:
        active_response = APIClient().post(url, {"email": user.email}, format="json")
        assert active_response.status_code == status.HTTP_200_OK
        assert send_mail_mock.called is True

    user.is_active = False
    user.save(update_fields=["is_active"])
    with patch("apps.accounts.views.EmailService.send_template_email") as send_mail_mock:
        inactive_response = APIClient().post(url, {"email": user.email}, format="json")
        assert inactive_response.status_code == status.HTTP_200_OK
        send_mail_mock.assert_not_called()


@pytest.mark.django_db
def test_password_reset_request_returns_success_for_unknown_email():
    url = reverse("accounts:password_reset_request")

    with patch("apps.accounts.views.EmailService.send_template_email") as send_mail_mock:
        response = APIClient().post(
            url,
            {"email": "unknown-user@test.com"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Password reset email sent."
    send_mail_mock.assert_not_called()


@pytest.mark.django_db
@override_settings(FRONTEND_URL="", MOBILE_DEEPLINK_SCHEME="campushub")
def test_password_reset_request_uses_mobile_deeplink_when_frontend_url_missing(user):
    url = reverse("accounts:password_reset_request")
    captured = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return True

    with patch(
        "apps.accounts.views.EmailService.send_template_email",
        side_effect=capture,
    ):
        response = APIClient().post(url, {"email": user.email}, format="json")

    assert response.status_code == status.HTTP_200_OK
    reset_url = captured["context"]["reset_url"]
    assert reset_url.startswith("campushub://reset-password?token=")
    assert captured["context"]["reset_link_expires_hours"] == 1


@pytest.mark.django_db
def test_password_reset_request_sends_email_to_outbox(user):
    mail.outbox.clear()
    url = reverse("accounts:password_reset_request")
    response = APIClient().post(url, {"email": user.email}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert "password reset" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
def test_password_reset_confirm_works_for_both_confirm_routes(user):
    token_for_uid_route = generate_signed_password_reset_token(user)
    uid_route_response = APIClient().post(
        reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": "ignored", "token": token_for_uid_route},
        ),
        {"new_password": "newsecurepass123", "new_password_confirm": "newsecurepass123"},
        format="json",
    )
    assert uid_route_response.status_code == status.HTTP_200_OK

    token_only_response = APIClient().post(
        reverse(
            "accounts:password_reset_confirm_token",
            kwargs={"token": generate_signed_password_reset_token(user)},
        ),
        {"new_password": "anotherpass123", "new_password_confirm": "anotherpass123"},
        format="json",
    )
    assert token_only_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_email_verification_view_success_and_invalid_token(user):
    valid_response = APIClient().get(
        reverse(
            "accounts:verify_email",
            kwargs={"token": generate_signed_verification_token(user)},
        )
    )
    assert valid_response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_verified is True

    invalid_response = APIClient().get(
        reverse("accounts:verify_email", kwargs={"token": "invalid-token"})
    )
    assert invalid_response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_resend_verification_email_behaviour(user):
    mail.outbox.clear()

    missing_email = APIClient().post(
        reverse("accounts:resend_verify_email"), {}, format="json"
    )
    assert missing_email.status_code == status.HTTP_400_BAD_REQUEST

    user.is_verified = False
    user.save(update_fields=["is_verified"])
    resend = APIClient().post(
        reverse("accounts:resend_verify_email"),
        {"email": user.email},
        format="json",
    )
    assert resend.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1

    user.is_verified = True
    user.save(update_fields=["is_verified"])
    APIClient().post(
        reverse("accounts:resend_verify_email"),
        {"email": user.email},
        format="json",
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_user_viewset_filters_and_user_activity_scope(admin_user, user):
    admin_client = _auth_client(admin_user)
    other = User.objects.create_user(
        email="other-student@test.com",
        password="otherpass123",
        full_name="Other Student",
        registration_number="OTH001",
        role="STUDENT",
        is_verified=True,
    )
    User.objects.create_user(
        email="inactive@test.com",
        password="inactivepass123",
        full_name="Inactive User",
        registration_number="INA001",
        role="STUDENT",
        is_active=False,
    )

    role_filtered = admin_client.get("/api/auth/users/?role=STUDENT")
    assert role_filtered.status_code == status.HTTP_200_OK
    assert role_filtered.data["count"] >= 2

    active_filtered = admin_client.get("/api/auth/users/?is_active=false")
    assert active_filtered.status_code == status.HTTP_200_OK
    assert any(item["email"] == "inactive@test.com" for item in active_filtered.data["results"])

    verified_filtered = admin_client.get("/api/auth/users/?is_verified=true")
    assert verified_filtered.status_code == status.HTTP_200_OK
    assert any(item["email"] == other.email for item in verified_filtered.data["results"])

    searched = admin_client.get("/api/auth/users/?search=OTH001")
    assert searched.status_code == status.HTTP_200_OK
    assert any(item["email"] == other.email for item in searched.data["results"])

    UserActivity.objects.create(user=user, action="login", description="student login")
    UserActivity.objects.create(
        user=other, action="login", description="other student login"
    )
    student_client = _auth_client(user)
    activity_response = student_client.get("/api/auth/activities/")
    assert activity_response.status_code == status.HTTP_200_OK
    assert activity_response.data["count"] == 1


@pytest.mark.django_db
def test_profile_photo_upload_and_delete_branches(user):
    client = _auth_client(user)
    gif_bytes = (
        b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )
    image = SimpleUploadedFile("avatar.gif", gif_bytes, content_type="image/gif")
    upload = client.post(
        reverse("accounts:profile_photo_upload"),
        {"profile_image": image},
        format="multipart",
    )
    assert upload.status_code == status.HTTP_200_OK

    deleted = client.delete(reverse("accounts:profile_photo_delete"))
    assert deleted.status_code == status.HTTP_200_OK

    missing = client.delete(reverse("accounts:profile_photo_delete"))
    assert missing.status_code == status.HTTP_404_NOT_FOUND
