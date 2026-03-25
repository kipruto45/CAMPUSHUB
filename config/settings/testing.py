"""Django test settings."""

from datetime import timedelta

from .base import *  # noqa: F401, F403

DEBUG = True

# Keep test environment lean.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [
    mw for mw in MIDDLEWARE if mw != "debug_toolbar.middleware.DebugToolbarMiddleware"  # noqa: F405
]

# Fast, isolated test database.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",  # noqa: F405
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "campushub-test-cache",
    }
}

# Disable throttling during tests to avoid cache/redis dependency.
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = "/tmp/campushub_test_media"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory channel layer for isolated websocket tests.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Allow narrowing URL loading for targeted test runs.
ROOT_URLCONF = config("TEST_ROOT_URLCONF", default="config.urls")  # noqa: F405

# Encryption behavior for tests:
# keep encryption disabled but allow fallback plaintext marker so
# encrypted model fields can be created in fixtures/migrations.
ENCRYPTION_ENABLED = False
ENCRYPTION_ALLOW_FALLBACK = True
ENCRYPTION_WARN_ON_FALLBACK = False

# Keep logging simple during tests.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# Keep token checks deterministic for auth tests that validate short-lived
# admin impersonation access tokens.
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=30)  # noqa: F405
