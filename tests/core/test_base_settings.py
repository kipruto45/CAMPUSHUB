import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
import pytest

from config.settings import base as base_settings

def _patch_config_from_os_env(monkeypatch):
    def _config(key, default="", cast=None):
        value = os.environ.get(key, default)
        return cast(value) if cast else value

    monkeypatch.setattr(base_settings, "config", _config)


def test_database_from_url_parses_postgres_with_sslmode():
    db = base_settings._database_from_url(
        "postgresql://user:pass@db.local:5433/campus?sslmode=require"
    )

    assert db["ENGINE"] == "django.db.backends.postgresql"
    assert db["NAME"] == "campus"
    assert db["USER"] == "user"
    assert db["PASSWORD"] == "pass"
    assert db["HOST"] == "db.local"
    assert db["PORT"] == "5433"
    assert db["OPTIONS"]["sslmode"] == "require"


def test_database_from_url_parses_sqlite_memory():
    db = base_settings._database_from_url("sqlite:///:memory:")

    assert db == {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}


def test_database_from_url_rejects_unknown_scheme():
    with pytest.raises(ImproperlyConfigured):
        base_settings._database_from_url("mysql://user:pass@localhost:3306/campus")


def test_resolve_default_database_prefers_database_url_when_force_sqlite_disabled(
    monkeypatch,
):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", False)

    resolved = base_settings._resolve_default_database(
        "postgresql://user:pass@db.local:5433/campus?sslmode=require"
    )

    assert resolved["ENGINE"] == "django.db.backends.postgresql"
    assert resolved["NAME"] == "campus"
    assert resolved["HOST"] == "db.local"
    assert resolved["PORT"] == "5433"
    assert resolved["OPTIONS"]["sslmode"] == "require"


def test_resolve_default_database_uses_sqlite_url_when_supplied(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", True)

    resolved = base_settings._resolve_default_database(
        "sqlite:////tmp/campushub_resolve.sqlite3"
    )

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert resolved["NAME"] == "/tmp/campushub_resolve.sqlite3"


def test_resolve_default_database_uses_sqlite_in_development_without_database_url(
    monkeypatch,
):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", True)
    monkeypatch.setattr(base_settings, "ENVIRONMENT", "development")
    monkeypatch.delenv("SQLITE_PATH", raising=False)

    resolved = base_settings._resolve_default_database("")

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert Path(resolved["NAME"]) == base_settings.BASE_DIR / "db.sqlite3"


def test_resolve_default_database_respects_sqlite_path(
    monkeypatch,
):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", True)
    monkeypatch.setattr(base_settings, "ENVIRONMENT", "development")
    monkeypatch.setenv("SQLITE_PATH", "var/test-db.sqlite3")

    resolved = base_settings._resolve_default_database("")

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert Path(resolved["NAME"]) == base_settings.BASE_DIR / "var/test-db.sqlite3"


def test_resolve_default_database_uses_memory_sqlite_when_configured(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", True)
    monkeypatch.setenv("SQLITE_PATH", ":memory:")

    resolved = base_settings._resolve_default_database("")

    assert resolved == {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}


def test_resolve_default_database_uses_tmp_sqlite_in_production_without_database_url(
    monkeypatch,
):
    _patch_config_from_os_env(monkeypatch)
    monkeypatch.setattr(base_settings, "FORCE_SQLITE", True)
    monkeypatch.setattr(base_settings, "ENVIRONMENT", "production")
    monkeypatch.delenv("SQLITE_PATH", raising=False)

    resolved = base_settings._resolve_default_database("")

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert resolved["NAME"] == "/tmp/campushub.sqlite3"
