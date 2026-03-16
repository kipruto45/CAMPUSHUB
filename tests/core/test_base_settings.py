import os

from django.core.exceptions import ImproperlyConfigured
import pytest

from config.settings import base as base_settings


DB_ENV_KEYS = [
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]


def _clear_db_env(monkeypatch):
    for key in DB_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


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


def test_should_use_postgres_false_without_flags(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.delenv("USE_POSTGRES", raising=False)
    monkeypatch.delenv("DB_ENGINE", raising=False)
    assert base_settings._should_use_postgres_in_non_production() is False


def test_should_use_postgres_true_with_use_postgres_flag(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("USE_POSTGRES", "true")
    assert base_settings._should_use_postgres_in_non_production() is True


def test_should_use_postgres_true_with_db_engine(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DB_ENGINE", "postgresql")
    assert base_settings._should_use_postgres_in_non_production() is True


def test_resolve_default_database_prefers_database_url(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("USE_POSTGRES", "true")
    monkeypatch.setenv("DB_NAME", "ignored_pg_db")

    resolved = base_settings._resolve_default_database(
        "development",
        "sqlite:////tmp/campushub_resolve.sqlite3",
    )

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert resolved["NAME"] == "/tmp/campushub_resolve.sqlite3"


def test_resolve_default_database_uses_sqlite_in_development_without_db_env(
    monkeypatch,
):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.delenv("USE_POSTGRES", raising=False)
    monkeypatch.delenv("DB_ENGINE", raising=False)

    resolved = base_settings._resolve_default_database("development", "")

    assert resolved["ENGINE"] == "django.db.backends.sqlite3"
    assert str(resolved["NAME"]).endswith("dev_db.sqlite3")


def test_resolve_default_database_uses_postgres_when_db_env_present(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("USE_POSTGRES", "true")
    monkeypatch.setenv("DB_NAME", "campus_pg")
    monkeypatch.setenv("DB_USER", "campus_user")
    monkeypatch.setenv("DB_PASSWORD", "campus_pass")

    resolved = base_settings._resolve_default_database("development", "")

    assert resolved["ENGINE"] == "django.db.backends.postgresql"
    assert resolved["NAME"] == "campus_pg"
    assert resolved["USER"] == "campus_user"
    assert resolved["PASSWORD"] == "campus_pass"


def test_resolve_default_database_uses_postgres_in_production_by_default(monkeypatch):
    _patch_config_from_os_env(monkeypatch)
    _clear_db_env(monkeypatch)

    resolved = base_settings._resolve_default_database("production", "")

    assert resolved["ENGINE"] == "django.db.backends.postgresql"
    assert resolved["HOST"] == "localhost"
    assert resolved["PORT"] == "5432"
