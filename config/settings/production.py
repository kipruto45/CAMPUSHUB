"""
Django production settings.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in config("ALLOWED_HOSTS", default="").split(",")
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production.")

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = config(
    "SECURE_SSL_REDIRECT",
    default="true",
    cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if origin.strip()
]

# Production-specific logging
default_log_file = "/var/log/campushub/django.log"
log_file = config("DJANGO_LOG_FILE", default=default_log_file)
try:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    LOGGING["handlers"]["file"]["filename"] = log_file  # noqa: F405
except OSError:
    fallback_log = str(BASE_DIR / "logs" / "django.log")  # noqa: F405
    Path(fallback_log).parent.mkdir(parents=True, exist_ok=True)
    LOGGING["handlers"]["file"]["filename"] = fallback_log  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # noqa: F405

# Cache configuration for production
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# Email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Sentry or other error tracking can be configured here
# SENTRY_DSN = config('SENTRY_DSN', default='')
# if SENTRY_DSN:
#     import sentry_sdk
#     from sentry_sdk.integrations.django import DjangoIntegration
#     sentry_sdk.init(dsn=SENTRY_DSN, integrations=[DjangoIntegration()])
