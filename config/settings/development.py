"""
Django development settings.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Development-specific settings
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

# Enable debug toolbar in development
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware"
] + MIDDLEWARE  # noqa: F405

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
}

# Email backend:
# - defaults from base settings (console backend unless overridden by env)
# - if you set EMAIL_BACKEND to SMTP in .env, real email delivery works in development

# More verbose logging for development
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405
