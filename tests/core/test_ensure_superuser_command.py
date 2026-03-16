"""Tests for ensure_superuser management command."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_ensure_superuser_creates_user_from_args():
    user_model = get_user_model()
    out = StringIO()

    call_command(
        "ensure_superuser",
        "--email",
        "owner@example.com",
        "--password",
        "StrongPass123!",
        "--full-name",
        "Owner Admin",
        stdout=out,
    )

    user = user_model.objects.get(email="owner@example.com")
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.is_active is True
    assert user.role == "ADMIN"
    assert user.full_name == "Owner Admin"
    assert user.check_password("StrongPass123!") is True


@pytest.mark.django_db
def test_ensure_superuser_promotes_existing_user_and_updates_password():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="existing@example.com",
        password="OldPass123!",
        full_name="Existing User",
        role="STUDENT",
    )
    assert user.is_superuser is False

    out = StringIO()
    call_command(
        "ensure_superuser",
        "--email",
        "existing@example.com",
        "--password",
        "NewPass123!",
        "--full-name",
        "Existing Admin",
        "--update-password",
        stdout=out,
    )

    user.refresh_from_db()
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.role == "ADMIN"
    assert user.full_name == "Existing Admin"
    assert user.check_password("NewPass123!") is True


@pytest.mark.django_db
def test_ensure_superuser_reads_env_vars(monkeypatch):
    user_model = get_user_model()
    out = StringIO()

    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "envadmin@example.com")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "EnvPass123!")
    monkeypatch.setenv("DJANGO_SUPERUSER_FULL_NAME", "Env Admin")

    call_command("ensure_superuser", stdout=out)

    user = user_model.objects.get(email="envadmin@example.com")
    assert user.is_superuser is True
    assert user.full_name == "Env Admin"
    assert user.check_password("EnvPass123!") is True


@pytest.mark.django_db
def test_ensure_superuser_requires_password(monkeypatch):
    out = StringIO()
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "missingpass@example.com")
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    with pytest.raises(CommandError):
        call_command("ensure_superuser", stdout=out)
