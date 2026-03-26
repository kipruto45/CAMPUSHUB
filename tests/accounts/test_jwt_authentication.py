"""Tests for custom JWT authentication helpers."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.authentication import JWTAuthentication, generate_tokens_for_user


@pytest.mark.django_db
def test_generate_tokens_for_user_default_and_remember_me(user):
    default_tokens = generate_tokens_for_user(user, remember_me=False)
    remember_tokens = generate_tokens_for_user(user, remember_me=True)

    default_refresh = RefreshToken(default_tokens["refresh"])
    remember_refresh = RefreshToken(remember_tokens["refresh"])

    assert "access" in default_tokens and "refresh" in default_tokens
    assert "access" in remember_tokens and "refresh" in remember_tokens

    default_exp = datetime.fromtimestamp(default_refresh["exp"], tz=timezone.utc)
    remember_exp = datetime.fromtimestamp(remember_refresh["exp"], tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    default_days = (default_exp - now).days
    remember_days = (remember_exp - now).days
    assert 0 <= default_days <= 2
    assert 25 <= remember_days <= 31


@pytest.mark.django_db
def test_get_user_returns_active_user(user):
    authentication = JWTAuthentication()
    token = {"user_id": str(user.id)}

    resolved = authentication.get_user(token)
    assert resolved.id == user.id


@pytest.mark.django_db
def test_get_user_raises_for_missing_user_id():
    authentication = JWTAuthentication()
    with pytest.raises(InvalidToken, match="Token contained no recognizable"):
        authentication.get_user({})


@pytest.mark.django_db
def test_get_user_raises_for_missing_user_record():
    authentication = JWTAuthentication()
    with pytest.raises(InvalidToken, match="User not found"):
        authentication.get_user({"user_id": 999999})


@pytest.mark.django_db
def test_get_user_raises_for_inactive_user(user):
    user.is_active = False
    user.save(update_fields=["is_active"])
    authentication = JWTAuthentication()

    with pytest.raises(AuthenticationFailed, match="disabled"):
        authentication.get_user({"user_id": str(user.id)})


@pytest.mark.django_db
def test_get_user_wraps_unexpected_errors(user):
    authentication = JWTAuthentication()

    with patch(
        "apps.accounts.authentication.User.objects.get",
        side_effect=RuntimeError("database unavailable"),
    ):
        with pytest.raises(InvalidToken, match="database unavailable"):
            authentication.get_user({"user_id": str(user.id)})


@pytest.mark.django_db
def test_authenticate_returns_none_without_header():
    authentication = JWTAuthentication()
    request = APIRequestFactory().get("/api/auth/me/")

    assert authentication.authenticate(request) is None


@pytest.mark.django_db
def test_authenticate_returns_none_for_invalid_token():
    authentication = JWTAuthentication()
    request = APIRequestFactory().get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION="Bearer invalid-token",
    )

    assert authentication.authenticate(request) is None


@pytest.mark.django_db
def test_authenticate_returns_user_and_token_for_valid_bearer_token(user):
    authentication = JWTAuthentication()
    access = str(RefreshToken.for_user(user).access_token)
    request = APIRequestFactory().get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )

    result = authentication.authenticate(request)
    assert result is not None
    assert result[0].id == user.id
