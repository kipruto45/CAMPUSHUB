"""Tests for social auth service logic."""

from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from apps.accounts.models import LinkedAccount, Profile
from apps.accounts.social_auth import (SocialAuthService,
                                       get_google_provider_config,
                                       get_microsoft_provider_config)

User = get_user_model()


@pytest.mark.django_db
def test_import_profile_image_uses_image_bytes_without_url(user):
    assert user.profile_image.name == "defaults/profile.png"

    SocialAuthService._import_profile_image(
        user=user,
        provider="microsoft",
        image_bytes=b"fake-image",
        content_type="image/png",
    )
    user.refresh_from_db()

    assert user.profile_image.name != "defaults/profile.png"
    assert user.profile_image.name.endswith(".png")


@pytest.mark.django_db
def test_import_profile_image_skips_when_user_has_custom_image(user):
    user.profile_image.save("custom.jpg", ContentFile(b"custom"), save=True)
    original_name = user.profile_image.name

    SocialAuthService._import_profile_image(
        user=user,
        provider="google",
        image_url="https://example.com/new.png",
        image_bytes=b"new-image",
        content_type="image/png",
    )
    user.refresh_from_db()

    assert user.profile_image.name == original_name


@pytest.mark.django_db
def test_process_google_user_requires_email():
    with pytest.raises(
        ValueError,
        match="Email is required from Google OAuth",
    ):
        SocialAuthService.process_google_user({"name": "No Email"})


@pytest.mark.django_db
def test_process_google_user_creates_user_profile_and_links(monkeypatch):
    link_calls = {}
    monkeypatch.setattr(
        SocialAuthService,
        "_import_profile_image",
        lambda **kwargs: None,
    )

    def fake_link_account(**kwargs):
        link_calls["kwargs"] = kwargs
        return None

    monkeypatch.setattr(
        "apps.accounts.social_auth.LinkedAccountService.link_account",
        fake_link_account,
    )

    user = SocialAuthService.process_google_user(
        {
            "email": "google_new@test.com",
            "name": "Google User",
            "first_name": "Google",
            "last_name": "User",
            "picture": "https://example.com/avatar.jpg",
            "sub": "google-sub-1",
        }
    )

    assert user.email == "google_new@test.com"
    assert user.auth_provider == "google"
    assert user.is_verified is True
    assert Profile.objects.filter(user=user).exists()
    assert link_calls["kwargs"]["provider"] == "google"
    assert link_calls["kwargs"]["provider_user_id"] == "google-sub-1"


@pytest.mark.django_db
def test_process_google_user_updates_existing_user(monkeypatch, user):
    user.auth_provider = "email"
    user.first_name = "Old"
    user.last_name = "Name"
    user.save(
        update_fields=[
            "auth_provider",
            "first_name",
            "last_name",
            "updated_at",
        ]
    )
    monkeypatch.setattr(
        SocialAuthService,
        "_import_profile_image",
        lambda **kwargs: None,
    )

    updated = SocialAuthService.process_google_user(
        {
            "email": user.email,
            "name": "New Name",
            "first_name": "New",
            "last_name": "Name",
            "sub": "google-sub-2",
        }
    )
    updated.refresh_from_db()

    assert updated.first_name == "New"
    assert updated.last_name == "Name"
    assert updated.full_name == "New Name"
    assert updated.auth_provider == "email"
    assert LinkedAccount.objects.filter(
        user=updated,
        provider="google",
        provider_user_id="google-sub-2",
        is_active=True,
    ).exists()


@pytest.mark.django_db
def test_process_microsoft_user_requires_email():
    with pytest.raises(
        ValueError,
        match="Email is required from Microsoft OAuth",
    ):
        SocialAuthService.process_microsoft_user({"displayName": "No Email"})


@pytest.mark.django_db
def test_process_microsoft_user_uses_fallback_email_and_links(monkeypatch):
    import_calls = {}
    monkeypatch.setattr(
        SocialAuthService,
        "_import_profile_image",
        lambda **kwargs: import_calls.update(kwargs),
    )

    user = SocialAuthService.process_microsoft_user(
        {
            "mail": "microsoft_new@test.com",
            "displayName": "Microsoft User",
            "givenName": "Microsoft",
            "surname": "User",
            "id": "microsoft-id-1",
            "photo_content": b"img",
            "photo_content_type": "image/png",
        }
    )

    assert user.email == "microsoft_new@test.com"
    assert user.auth_provider == "microsoft"
    assert user.is_verified is True
    assert Profile.objects.filter(user=user).exists()
    assert import_calls["image_bytes"] == b"img"
    assert LinkedAccount.objects.filter(
        user=user,
        provider="microsoft",
        provider_user_id="microsoft-id-1",
        is_active=True,
    ).exists()


@pytest.mark.django_db
def test_generate_tokens_for_social_user_returns_access_and_refresh(user):
    tokens = SocialAuthService.generate_tokens_for_social_user(user)

    assert "access" in tokens
    assert "refresh" in tokens
    assert tokens["access"]
    assert tokens["refresh"]


def test_provider_config_helpers_expose_required_keys(settings):
    settings.SOCIAL_AUTH_GOOGLE_CLIENT_ID = "g-id"
    settings.SOCIAL_AUTH_GOOGLE_CLIENT_SECRET = "g-secret"
    settings.SOCIAL_AUTH_GOOGLE_REDIRECT_URI = "http://localhost/google"
    settings.SOCIAL_AUTH_MICROSOFT_CLIENT_ID = "m-id"
    settings.SOCIAL_AUTH_MICROSOFT_CLIENT_SECRET = "m-secret"
    settings.SOCIAL_AUTH_MICROSOFT_REDIRECT_URI = "http://localhost/microsoft"

    google = get_google_provider_config()
    microsoft = get_microsoft_provider_config()

    assert google["client_id"] == "g-id"
    assert "token_url" in google
    assert microsoft["client_id"] == "m-id"
    assert "userinfo_url" in microsoft


def test_import_profile_image_handles_request_failures(monkeypatch, user):
    def failing_get(*args, **kwargs):
        raise RuntimeError("network down")

    with mock.patch("apps.accounts.social_auth.requests.get", failing_get):
        SocialAuthService._import_profile_image(
            user=user,
            provider="google",
            image_url="https://example.com/avatar.jpg",
        )

    user.refresh_from_db()
    assert user.profile_image.name == "defaults/profile.png"
