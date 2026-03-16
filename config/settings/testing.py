"""Django test settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

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
