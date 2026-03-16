"""Tests for production_readiness_check management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


PROD_SECRET = "pR0dStrongSecretKey_1234567890abcdefghijklmnopqrstuvwxyzXYZ"
PROD_OVERRIDES = dict(
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_SSL_REDIRECT=True,
    SECURE_HSTS_SECONDS=31536000,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    CELERY_BROKER_URL="redis://localhost:6379/0",
    CELERY_RESULT_BACKEND="redis://localhost:6379/0",
)
PROD_OVERRIDES_WITH_CONSOLE_EMAIL = {
    **PROD_OVERRIDES,
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
}


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local", "campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local", "https://campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES,
)
def test_production_readiness_passes_with_allow_sqlite():
    out = StringIO()
    call_command("production_readiness_check", "--allow-sqlite", stdout=out)
    output = out.getvalue()
    assert "Production readiness summary: failures=0" in output
    assert "[OK] environment - production" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="development",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES,
)
def test_production_readiness_fails_if_environment_is_not_production():
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("production_readiness_check", "--allow-sqlite", stdout=out)
    output = out.getvalue()
    assert "[FAIL] environment" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES,
)
def test_production_readiness_strict_push_fails_without_provider():
    out = StringIO()
    with pytest.raises(CommandError):
        call_command(
            "production_readiness_check",
            "--allow-sqlite",
            "--strict-push",
            stdout=out,
        )
    output = out.getvalue()
    assert "[FAIL] push_strict" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES,
)
def test_production_readiness_require_superuser_fails_when_missing():
    out = StringIO()
    with pytest.raises(CommandError):
        call_command(
            "production_readiness_check",
            "--allow-sqlite",
            "--require-superuser",
            stdout=out,
        )
    output = out.getvalue()
    assert "[FAIL] superuser" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES,
)
def test_production_readiness_handles_database_failure_without_traceback(monkeypatch):
    from apps.core.management.commands.production_readiness_check import Command

    def fake_db_check(ok, fail):
        fail("database_connectivity", "simulated failure")
        return False

    monkeypatch.setattr(
        Command,
        "_check_database_connectivity",
        staticmethod(fake_db_check),
    )

    out = StringIO()
    with pytest.raises(CommandError):
        call_command("production_readiness_check", "--allow-sqlite", stdout=out)
    output = out.getvalue()
    assert "[FAIL] database_connectivity - simulated failure" in output
    assert "[FAIL] migrations - skipped because database connectivity failed" in output
    assert "[WARN] superuser - skipped because database connectivity failed" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    SECURE_SSL_REDIRECT=False,
    SECURE_HSTS_SECONDS=0,
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    CELERY_BROKER_URL="redis://localhost:6379/0",
    CELERY_RESULT_BACKEND="redis://localhost:6379/0",
)
def test_production_readiness_fails_for_insecure_transport_settings():
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("production_readiness_check", "--allow-sqlite", stdout=out)
    output = out.getvalue()
    assert "[FAIL] secure_cookies" in output
    assert "[FAIL] ssl_redirect" in output
    assert "[FAIL] hsts" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="production",
    DEBUG=False,
    SECRET_KEY=PROD_SECRET,
    ALLOWED_HOSTS=["api.campushub.local"],
    CSRF_TRUSTED_ORIGINS=["https://api.campushub.local"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://localhost:6379/0"]},
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "prod-readiness-test",
        }
    },
    FCM_ENABLED=False,
    APNS_ENABLED=False,
    **PROD_OVERRIDES_WITH_CONSOLE_EMAIL,
)
def test_production_readiness_fails_for_console_email_backend():
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("production_readiness_check", "--allow-sqlite", stdout=out)
    output = out.getvalue()
    assert "[FAIL] email_backend" in output
