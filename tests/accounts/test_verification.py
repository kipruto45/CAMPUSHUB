"""Tests for verification token models and helpers."""

from datetime import timedelta

import pytest
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.accounts import verification
from apps.accounts.verification import (EmailVerificationToken,
                                        PasswordResetToken)


@pytest.mark.django_db
def test_email_verification_token_generation_and_url(user):
    token = EmailVerificationToken.generate_token(user)

    assert token.user == user
    assert len(token.token) == 64
    assert token.is_valid() is True
    assert token.get_verification_url("campushub.test") == (
        f"https://campushub.test/api/auth/verify-email/{token.token}/"
    )


@pytest.mark.django_db
def test_email_verification_token_invalid_when_used_or_expired(user):
    token = EmailVerificationToken.generate_token(user)

    token.is_used = True
    token.save(update_fields=["is_used"])
    assert token.is_valid() is False

    token.is_used = False
    token.expires_at = timezone.now() - timedelta(minutes=1)
    token.save(update_fields=["is_used", "expires_at"])
    assert token.is_valid() is False


@pytest.mark.django_db
def test_password_reset_token_generation_and_url(user):
    token = PasswordResetToken.generate_token(user)

    assert token.user == user
    assert len(token.token) == 64
    assert token.is_valid() is True
    reset_url = (
        "https://campushub.test/api/auth/password/reset/confirm/"
        f"{token.token}/"
    )
    assert token.get_reset_url("campushub.test") == (
        reset_url
    )


@pytest.mark.django_db
def test_password_reset_token_invalid_when_used_or_expired(user):
    token = PasswordResetToken.generate_token(user)

    token.is_used = True
    token.save(update_fields=["is_used"])
    assert token.is_valid() is False

    token.is_used = False
    token.expires_at = timezone.now() - timedelta(minutes=1)
    token.save(update_fields=["is_used", "expires_at"])
    assert token.is_valid() is False


@pytest.mark.django_db
def test_signed_verification_token_round_trip(user):
    token = verification.generate_signed_verification_token(user)
    resolved = verification.validate_signed_verification_token(token)

    assert resolved == user


@pytest.mark.django_db
def test_signed_verification_token_invalid_cases(user, monkeypatch):
    assert (
        verification.validate_signed_verification_token("invalid-token")
        is None
    )

    token = verification.generate_signed_verification_token(user)
    assert (
        verification.validate_signed_verification_token(
            token,
            max_age_seconds=-1,
        )
        is None
    )

    monkeypatch.setattr(
        verification.signing,
        "loads",
        lambda *args, **kwargs: {"user_id": None, "email": None},
    )
    assert verification.validate_signed_verification_token("anything") is None


@pytest.mark.django_db
def test_signed_verification_token_inactive_user_returns_none(user):
    token = verification.generate_signed_verification_token(user)
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert verification.validate_signed_verification_token(token) is None


@pytest.mark.django_db
def test_signed_verification_token_handles_object_does_not_exist(monkeypatch):
    token = verification.generate_signed_verification_token(
        type("UserStub", (), {"id": "1", "email": "x@y.com"})()
    )

    def raise_missing(*args, **kwargs):
        raise ObjectDoesNotExist()

    monkeypatch.setattr(verification.User.objects, "filter", raise_missing)

    assert verification.validate_signed_verification_token(token) is None


@pytest.mark.django_db
def test_signed_password_reset_token_round_trip(user):
    token = verification.generate_signed_password_reset_token(user)
    resolved = verification.validate_signed_password_reset_token(token)

    assert resolved == user


@pytest.mark.django_db
def test_signed_password_reset_token_invalid_cases(user, monkeypatch):
    assert (
        verification.validate_signed_password_reset_token("invalid-token")
        is None
    )

    token = verification.generate_signed_password_reset_token(user)
    assert (
        verification.validate_signed_password_reset_token(
            token,
            max_age_seconds=-1,
        )
        is None
    )

    monkeypatch.setattr(
        verification.signing,
        "loads",
        lambda *args, **kwargs: {"user_id": None, "email": None},
    )
    assert (
        verification.validate_signed_password_reset_token("anything")
        is None
    )


@pytest.mark.django_db
def test_signed_password_reset_token_handles_object_does_not_exist(
    monkeypatch,
):
    token = signing.dumps(
        {"user_id": "1", "email": "x@y.com", "ts": timezone.now().timestamp()},
        salt=verification.PASSWORD_RESET_SALT,
    )

    def raise_missing(*args, **kwargs):
        raise ObjectDoesNotExist()

    monkeypatch.setattr(verification.User.objects, "filter", raise_missing)

    assert verification.validate_signed_password_reset_token(token) is None
