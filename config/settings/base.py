"""
Django base settings for CampusHub project.
"""

from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from decouple import config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENVIRONMENT = config("ENVIRONMENT", default="development").strip().lower()
FORCE_SQLITE = config(
    "FORCE_SQLITE",
    default="true",
    cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
)

# SECURITY WARNING: keep the secret key used in production secret!
_INSECURE_DEV_SECRET = "django-insecure-dev-key-change-in-production"
SECRET_KEY = config("SECRET_KEY", default=_INSECURE_DEV_SECRET)


def _has_weak_secret_key(secret_key: str) -> bool:
    """Mirror Django deploy checks and fail fast in production."""
    if len(secret_key) < 50:
        return True
    if len(set(secret_key)) < 5:
        return True
    return secret_key.startswith("django-insecure-")


if ENVIRONMENT == "production" and (
    not SECRET_KEY
    or SECRET_KEY == _INSECURE_DEV_SECRET
    or _has_weak_secret_key(SECRET_KEY)
):
    raise ImproperlyConfigured(
        (
            "SECRET_KEY must be a strong production secret "
            "(>=50 chars, high entropy, not django-insecure-...)."
        )
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config(
    "DEBUG",
    default="false",
    cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
)

# Maintenance Mode Configuration
MAINTENANCE_MODE = config(
    "MAINTENANCE_MODE",
    default="false",
    cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
)
MAINTENANCE_MESSAGE = config(
    "MAINTENANCE_MESSAGE",
    default="The app is currently under maintenance. Please try again later.",
)
MAINTENANCE_ALLOWED_IPS = config(
    "MAINTENANCE_ALLOWED_IPS",
    default="",
)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Application definition
DJANGO_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "cloudinary_storage",
    "django_celery_beat",
    "phonenumber_field",
    "channels",
    "graphene_django",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.ai.apps.AIConfig",
    "apps.faculties",
    "apps.courses",
    "apps.calendar",
    "apps.calendar_sync",
    "apps.resources",
    "apps.bookmarks",
    "apps.comments",
    "apps.ratings",
    "apps.downloads",
    "apps.notifications",
    "apps.search",
    "apps.analytics",
    "apps.learning_analytics",
    "apps.moderation",
    "apps.reports",
    "apps.dashboard",
    "apps.activity",
    "apps.favorites",
    "apps.announcements",
    "apps.library",
    "apps.admin_management",
    "apps.recommendations",
    "apps.gamification",
    "apps.social",
    "apps.payments",
    "apps.two_factor",
    "apps.graphql",
    "apps.cloud_storage",
    "apps.integrations",
    "apps.integrations.google_classroom",
    "apps.integrations.microsoft_teams",
    "apps.institutions",
    "apps.peer_tutoring",
    "apps.live_rooms",
    "apps.notes",
    "apps.referrals",
    "apps.certificates",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "apps.core.middleware.APIVersionHeadersMiddleware",
    "apps.api.middleware.APIAnalyticsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.APIUsageLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
def _database_from_url(database_url: str) -> dict:
    """Parse DATABASE_URL into Django DATABASES['default'] format."""
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()

    if scheme in {"postgres", "postgresql", "pgsql"}:
        db_config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote((parsed.path or "").lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": str(parsed.port or 5432),
        }
    elif scheme in {"sqlite", "sqlite3"}:
        sqlite_path = unquote(parsed.path or "")
        if sqlite_path in {"", "/", ":memory:", "/:memory:"}:
            name = ":memory:"
        elif sqlite_path.startswith("//"):
            name = sqlite_path[1:]
        else:
            name = sqlite_path
        db_config = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": name,
        }
    else:
        raise ImproperlyConfigured(
            (
                f"Unsupported DATABASE_URL scheme '{scheme}'. "
                "Supported: postgresql, sqlite."
            )
        )

    query = parse_qs(parsed.query or "")
    options = {}
    if "sslmode" in query and query["sslmode"]:
        options["sslmode"] = query["sslmode"][-1]
    if options:
        db_config["OPTIONS"] = options
    return db_config


def _resolve_default_database(database_url: str) -> dict:
    is_sqlite_url = database_url.lower().startswith(("sqlite://", "sqlite3://"))

    if database_url and not FORCE_SQLITE:
        return _database_from_url(database_url)
    if database_url and is_sqlite_url:
        return _database_from_url(database_url)

    sqlite_path_env = config("SQLITE_PATH", default="").strip()
    if sqlite_path_env in {":memory:", "/:memory:"}:
        sqlite_name = ":memory:"
    elif sqlite_path_env:
        sqlite_path = Path(sqlite_path_env).expanduser()
        if not sqlite_path.is_absolute():
            sqlite_path = BASE_DIR / sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_name = str(sqlite_path)
    elif ENVIRONMENT == "production":
        sqlite_path = Path("/tmp/campushub.sqlite3")
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_name = str(sqlite_path)
    else:
        sqlite_path = BASE_DIR / "db.sqlite3"
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_name = str(sqlite_path)

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": sqlite_name,
    }


DATABASE_URL = config("DATABASE_URL", default="").strip()
default_database = _resolve_default_database(DATABASE_URL)

DATABASES = {
    "default": default_database,
}

# Create SQLite database file if it doesn't exist
if default_database.get("ENGINE") == "django.db.backends.sqlite3":
    db_path = default_database.get("NAME", "")
    if db_path and db_path != ":memory:":
        db_file = Path(db_path)
        if not db_file.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db_file.touch()

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = config("STATIC_URL", default="static/")
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = config("MEDIA_URL", default="media/")
MEDIA_ROOT = BASE_DIR / "media"

# Download configuration for mobile app
# Configure where downloaded files should be stored on the device
DOWNLOAD_DIRECTORY = config("DOWNLOAD_DIRECTORY", default="CampusHub/Downloads")
DOWNLOAD_TO_APP_DIRECTORY = config("DOWNLOAD_TO_APP_DIRECTORY", default="true", cast=lambda x: x.lower() in ("true", "1", "yes"))

# Prevent downloads from appearing in phone's general downloads folder
PREVENT_SYSTEM_DOWNLOADS = config("PREVENT_SYSTEM_DOWNLOADS", default="true", cast=lambda x: x.lower() in ("true", "1", "yes"))

# Default storage limit for users (in MB)
DEFAULT_STORAGE_LIMIT_MB = config("DEFAULT_STORAGE_LIMIT_MB", default=100, cast=int)

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    # Throttling
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "user": "500/hour",
        "upload": "20/hour",
        "download": "100/hour",
        # Mobile API throttles
        "mobile_anon": "30/minute",
        "mobile_auth": "200/hour",
        "mobile_upload": "10/day",
        "mobile_download": "100/hour",
        "mobile_auth_attempt": "10/minute",
        "mobile_authenticated": "500/hour",
        "burst": "60/minute",
        "sustained": "200/hour",
        "ip_based": "100/minute",
        "device": "300/hour",
    },
    # API Versioning
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1", "v2"],
    "VERSION_PARAM": "v",
}

# GraphQL configuration
GRAPHENE = {
    "SCHEMA": "apps.graphql.schema.schema",
}

# JWT Configuration
# Keep users logged in until they explicitly logout
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(config("JWT_ACCESS_TOKEN_LIFETIME", default=60))
    ),
    # Default refresh token lifetime (365 days) - user stays logged in for a year
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(config("JWT_REFRESH_TOKEN_LIFETIME", default=365))
    ),
    "ROTATE_REFRESH_TOKENS": True,  # Issue new refresh token on each use
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# Social Authentication
SOCIAL_AUTH_GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
SOCIAL_AUTH_GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
SOCIAL_AUTH_GOOGLE_REDIRECT_URI = config(
    "GOOGLE_REDIRECT_URI", default="http://localhost:8000/api/auth/google/callback/"
)

SOCIAL_AUTH_MICROSOFT_CLIENT_ID = config("MICROSOFT_CLIENT_ID", default="")
SOCIAL_AUTH_MICROSOFT_CLIENT_SECRET = config("MICROSOFT_CLIENT_SECRET", default="")
SOCIAL_AUTH_MICROSOFT_TENANT_ID = config("MICROSOFT_TENANT_ID", default="common")
SOCIAL_AUTH_MICROSOFT_REDIRECT_URI = config(
    "MICROSOFT_REDIRECT_URI",
    default="http://localhost:8000/api/auth/microsoft/callback/",
)

# Cloud Storage (Google Drive & OneDrive)
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_OAUTH_CLIENT_ID = config(
    "GOOGLE_OAUTH_CLIENT_ID",
    default=GOOGLE_CLIENT_ID,
)
GOOGLE_OAUTH_CLIENT_SECRET = config(
    "GOOGLE_OAUTH_CLIENT_SECRET",
    default=GOOGLE_CLIENT_SECRET,
)
GOOGLE_CLASSROOM_REDIRECT_URI = config(
    "GOOGLE_CLASSROOM_REDIRECT_URI",
    default="",
)
MICROSOFT_CLIENT_ID = config("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = config("MICROSOFT_CLIENT_SECRET", default="")
# Microsoft Teams OAuth (used for Teams integration)
MICROSOFT_OAUTH_CLIENT_ID = config(
    "MICROSOFT_OAUTH_CLIENT_ID",
    default=MICROSOFT_CLIENT_ID,
)
MICROSOFT_OAUTH_CLIENT_SECRET = config(
    "MICROSOFT_OAUTH_CLIENT_SECRET",
    default=MICROSOFT_CLIENT_SECRET,
)
MICROSOFT_TEAMS_REDIRECT_URI = config(
    "MICROSOFT_TEAMS_REDIRECT_URI",
    default="",
)
CLOUD_STORAGE_REDIRECT_URI = config(
    "CLOUD_STORAGE_REDIRECT_URI",
    default="campushub://auth/cloud/callback/",
)

# AI assistants and summarization
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
AI_CHAT_MODEL = config("AI_CHAT_MODEL", default="gpt-4o-mini")
AI_CHAT_TEMPERATURE = config("AI_CHAT_TEMPERATURE", default=0.4, cast=float)
AI_CHAT_MAX_TOKENS = config("AI_CHAT_MAX_TOKENS", default=500, cast=int)
AI_CHAT_TIMEOUT_SECONDS = config("AI_CHAT_TIMEOUT_SECONDS", default=25, cast=int)
SUMMARIZATION_MODEL = config("SUMMARIZATION_MODEL", default=AI_CHAT_MODEL)

# Payment provider configuration
PAYMENTS_ENABLED = config(
    "PAYMENTS_ENABLED",
    default="true",
    cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
)
BASE_URL = str(config("BASE_URL", default="http://localhost:8000")).strip().rstrip("/")

# Stripe
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

# PayPal
PAYPAL_MODE = str(config("PAYPAL_MODE", default="sandbox")).strip().lower() or "sandbox"
PAYPAL_CLIENT_ID = config("PAYPAL_CLIENT_ID", default="")
PAYPAL_CLIENT_SECRET = config("PAYPAL_CLIENT_SECRET", default="")
PAYPAL_TIMEOUT_SECONDS = config("PAYPAL_TIMEOUT_SECONDS", default=30, cast=int)

# Mobile money / M-Pesa
MOBILE_MONEY_PROVIDER = (
    str(config("MOBILE_MONEY_PROVIDER", default="mpesa")).strip().lower() or "mpesa"
)
MOBILE_MONEY_SHORT_CODE = str(config("MOBILE_MONEY_SHORT_CODE", default="")).strip()
MOBILE_MONEY_CONSUMER_KEY = str(config("MOBILE_MONEY_CONSUMER_KEY", default="")).strip()
MOBILE_MONEY_CONSUMER_SECRET = str(
    config("MOBILE_MONEY_CONSUMER_SECRET", default="")
).strip()
MOBILE_MONEY_PASSKEY = str(config("MOBILE_MONEY_PASSKEY", default="")).strip()
MOBILE_MONEY_ENV = (
    str(config("MOBILE_MONEY_ENV", default="sandbox")).strip().lower() or "sandbox"
)
MOBILE_MONEY_TRANSACTION_TYPE = (
    str(config("MOBILE_MONEY_TRANSACTION_TYPE", default="CustomerPayBillOnline")).strip()
    or "CustomerPayBillOnline"
)
MOBILE_MONEY_CALLBACK_URL = str(config("MOBILE_MONEY_CALLBACK_URL", default="")).strip()
MOBILE_MONEY_API_BASE_URL = str(config("MOBILE_MONEY_API_BASE_URL", default="")).strip()
MOBILE_MONEY_TIMEOUT_SECONDS = config(
    "MOBILE_MONEY_TIMEOUT_SECONDS",
    default=30,
    cast=int,
)

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default=(
        "http://localhost:3000,http://localhost:8081,http://localhost:19000,"
        "http://localhost:19001,exp://localhost:19000,exp://localhost:19001"
    ),
).split(",")
CORS_ALLOW_CREDENTIALS = True

# Allow all methods for mobile
CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
]

# Allow all headers for mobile
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-device-token",
    "x-device-id",
    "x-app-version",
]

# File Upload Configuration
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
MAX_FILE_SIZE = config("MAX_FILE_SIZE", default=52428800)  # 50MB
ALLOWED_FILE_EXTENSIONS = config(
    "ALLOWED_FILE_EXTENSIONS",
    default="pdf,doc,docx,ppt,pptx,xls,xlsx,txt,zip,rar,jpg,jpeg,png,gif",
).split(",")

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME = config("CLOUDINARY_CLOUD_NAME", default="")
CLOUDINARY_API_KEY = config("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = config("CLOUDINARY_API_SECRET", default="")

# Force local storage for now (Cloudinary disabled)
CLOUDINARY_ENABLED = False
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# Django 4.2+ storage configuration (replaces deprecated DEFAULT_FILE_STORAGE).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Firebase Cloud Messaging (FCM) Configuration
FCM_ENABLED = config(
    "FCM_ENABLED", default="false", cast=lambda x: x.lower() in ("true", "1", "yes")
)
FCM_SERVER_KEY = config("FCM_SERVER_KEY", default="")
FCM_PROJECT_ID = config("FCM_PROJECT_ID", default="campushub-80677")
FCM_SERVICE_ACCOUNT_PATH = config("FCM_SERVICE_ACCOUNT_PATH", default="")

# Apple Push Notification Service (APNs) Configuration
APNS_ENABLED = config(
    "APNS_ENABLED", default="false", cast=lambda x: x.lower() in ("true", "1", "yes")
)
APNS_KEY_ID = config("APNS_KEY_ID", default="")
APNS_TEAM_ID = config("APNS_TEAM_ID", default="")
APNS_BUNDLE_ID = config("APNS_BUNDLE_ID", default="com.campushub.app")
APNS_AUTH_KEY_PATH = config("APNS_AUTH_KEY_PATH", default="")
APNS_AUTH_KEY = config("APNS_AUTH_KEY", default="")
APNS_ENVIRONMENT = config(
    "APNS_ENVIRONMENT", default="development"
)  # development or production

# Mobile API Configuration
MOBILE_API_VERSION = str(config("MOBILE_API_VERSION", default="1.0")).strip() or "1.0"
MOBILE_DEEPLINK_SCHEME = config("MOBILE_DEEPLINK_SCHEME", default="campushub")
MOBILE_DEEPLINK_HOST = config("MOBILE_DEEPLINK_HOST", default="campushub.com")
FRONTEND_URL = config("FRONTEND_URL", default="")
_share_host = str(MOBILE_DEEPLINK_HOST).replace("https://", "").replace("http://", "")
RESOURCE_SHARE_BASE_URL = (
    str(config("RESOURCE_SHARE_BASE_URL", default=f"https://{_share_host}")).strip().rstrip("/")
)
ANDROID_APP_PACKAGE = config("ANDROID_APP_PACKAGE", default="com.campushub.app")
ANDROID_SHA256_CERT_FINGERPRINTS = [
    fingerprint.strip()
    for fingerprint in config("ANDROID_SHA256_CERT_FINGERPRINTS", default="").split(",")
    if fingerprint.strip()
]
IOS_TEAM_ID = config("IOS_TEAM_ID", default=APNS_TEAM_ID)
IOS_BUNDLE_ID = config("IOS_BUNDLE_ID", default=APNS_BUNDLE_ID)

# Sentry Configuration (Error Tracking)
SENTRY_DSN = config("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = config("SENTRY_ENVIRONMENT", default="production")
SENTRY_RELEASE = config("SENTRY_RELEASE", default="1.0.0")
SENTRY_TRACES_SAMPLE_RATE = config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float)
SENTRY_SESSIONS_SAMPLE_RATE = config(
    "SENTRY_SESSIONS_SAMPLE_RATE", default=0.1, cast=float
)
SENTRY_ERROR_SAMPLE_RATE = config("SENTRY_ERROR_SAMPLE_RATE", default=1.0, cast=float)
SENTRY_SEND_DEFAULT_PII = config(
    "SENTRY_SEND_DEFAULT_PII",
    default="false",
    cast=lambda x: str(x).lower() in ("true", "1", "yes"),
)

# Initialize Sentry (using the dedicated sentry module from apps.core)
from apps.core.sentry import init_sentry

init_sentry()

# =============================================================================
# Encryption Configuration
# End-to-end encryption for sensitive data at rest
# =============================================================================
# Enable/disable encryption feature
ENCRYPTION_ENABLED = config(
    "ENCRYPTION_ENABLED",
    default="false",
    cast=lambda x: str(x).lower() in ("true", "1", "yes"),
)

# Master key for encryption (should be 32 bytes / 64 hex characters for AES-256)
# In production, this MUST be set via environment variable and stored securely
ENCRYPTION_MASTER_KEY = config(
    "ENCRYPTION_MASTER_KEY",
    default="",
).strip()

# Key derivation salt (should be unique per deployment)
# This salt is used to derive user-specific keys from the master key
ENCRYPTION_KEY_SALT = config(
    "ENCRYPTION_KEY_SALT",
    default="campushub-default-salt-change-in-production",
).strip()

# Enable graceful degradation (allow unencrypted fallback for migration)
# When True, encryption failures will return unencrypted data instead of raising errors
ENCRYPTION_ALLOW_FALLBACK = config(
    "ENCRYPTION_ALLOW_FALLBACK",
    default="true",
    cast=lambda x: str(x).lower() in ("true", "1", "yes"),
)

# Key rotation settings
ENCRYPTION_KEY_VERSION = config(
    "ENCRYPTION_KEY_VERSION",
    default="1",
    cast=int,
)

# Store previous master keys for key rotation (comma-separated list)
# Format: version:hex_key (e.g., "1:oldkey,2:olderkey")
ENCRYPTION_PREVIOUS_KEYS = config(
    "ENCRYPTION_PREVIOUS_KEYS",
    default="",
).strip()

# Validate encryption settings
if ENCRYPTION_ENABLED and not ENCRYPTION_MASTER_KEY:
    import warnings
    warnings.warn(
        "ENCRYPTION_ENABLED is True but ENCRYPTION_MASTER_KEY is not set. "
        "Encryption will not work properly. Please set ENCRYPTION_MASTER_KEY.",
        UserWarning,
    )

if ENCRYPTION_MASTER_KEY and len(ENCRYPTION_MASTER_KEY) < 64:
    import warnings
    warnings.warn(
        "ENCRYPTION_MASTER_KEY should be at least 64 hex characters (32 bytes) "
        "for AES-256 encryption. Current length is insufficient for secure encryption.",
        UserWarning,
    )

_cloudinary_credentials_present = bool(
    CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET
)
# Force disable Cloudinary - use local file storage
CLOUDINARY_ENABLED = False

# Email Configuration
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@campushub.com")

# Celery Configuration (default to in-memory to avoid external services)
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="memory://")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="cache+memory://"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Nairobi"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    "cleanup-old-downloads": {
        "task": "apps.downloads.tasks.cleanup_old_downloads",
        "schedule": 86400,  # Daily
    },
    "update-trending-resources": {
        "task": "apps.resources.tasks.update_trending_resources",
        "schedule": 3600,  # Hourly
    },
    # Automation tasks
    "calculate-storage-usage": {
        "task": "apps.resources.automation_tasks.calculate_storage_usage",
        "schedule": 86400,  # Daily
    },
    "check-storage-warnings": {
        "task": "apps.resources.automation_tasks.check_storage_warnings",
        "schedule": 86400,  # Daily
    },
    "send-weekly-digest": {
        "task": "apps.resources.automation_tasks.send_weekly_digest",
        "schedule": 604800,  # Weekly (7 days)
    },
    "detect-duplicate-resources": {
        "task": "apps.resources.automation_tasks.detect_duplicate_resources",
        "schedule": 604800,  # Weekly
    },
    "moderation-stale-pending-alert": {
        "task": "apps.moderation.tasks.notify_stale_pending_resources",
        "schedule": 43200,  # Every 12 hours
    },
    "moderation-open-reports-alert": {
        "task": "apps.moderation.tasks.notify_open_reports",
        "schedule": 43200,  # Every 12 hours
    },
    # Google Classroom sync tasks
    "google-classroom-sync-all": {
        "task": "apps.integrations.google_classroom.tasks.sync_all_google_classroom_accounts",
        "schedule": 3600,  # Hourly
    },
    "google-classroom-refresh-tokens": {
        "task": "apps.integrations.google_classroom.tasks.refresh_expired_tokens",
        "schedule": 1800,  # Every 30 minutes
    },
}

# Cache configuration
CACHE_BACKEND = config("CACHE_BACKEND", default="locmem").strip().lower()
CACHE_REDIS_URL = config("REDIS_URL", default="").strip()

if CACHE_BACKEND == "redis" and CACHE_REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_REDIS_URL,
        }
    }
else:
    # Force safe fallback
    CACHE_BACKEND = "locmem"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"campushub-{ENVIRONMENT}-cache",
        }
    }

# Channels Configuration (WebSockets)
CHANNEL_LAYER_BACKEND = config(
    "CHANNEL_LAYER_BACKEND", default="inmemory"
).strip().lower()

if CHANNEL_LAYER_BACKEND == "redis" and CACHE_REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CACHE_REDIS_URL],
            },
        }
    }
else:
    # Force safe fallback
    CHANNEL_LAYER_BACKEND = "inmemory"
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

ASGI_APPLICATION = "config.asgi.application"

# Spectacular API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "CampusHub API",
    "DESCRIPTION": "University Learning Resources Management System API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Authentication", "description": "User authentication endpoints"},
        {"name": "Users", "description": "User management endpoints"},
        {"name": "Faculties", "description": "Faculty management endpoints"},
        {"name": "Departments", "description": "Department management endpoints"},
        {"name": "Courses", "description": "Course management endpoints"},
        {"name": "Units", "description": "Unit/Subject management endpoints"},
        {"name": "Resources", "description": "Learning resource endpoints"},
        {"name": "Bookmarks", "description": "Resource bookmark endpoints"},
        {"name": "Comments", "description": "Resource comment endpoints"},
        {"name": "Ratings", "description": "Resource rating endpoints"},
        {"name": "Downloads", "description": "Resource download endpoints"},
        {"name": "Notifications", "description": "Notification endpoints"},
        {"name": "Search", "description": "Resource search endpoints"},
        {"name": "Analytics", "description": "Analytics and reporting endpoints"},
        {"name": "Moderation", "description": "Content moderation endpoints"},
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": False,
        "displayRequestDuration": True,
        "filter": True,
    },
    "ENUM_NAME_OVERRIDES": {
        "ResourceStatusEnum": "apps.resources.models.Resource.STATUS_CHOICES",
        "ResourceRequestStatusEnum": "apps.resources.models.ResourceRequest.STATUS_CHOICES",
        "CourseProgressStatusEnum": "apps.resources.models.CourseProgress.STATUS_CHOICES",
        "ReportStatusEnum": "apps.reports.models.Report.STATUS_CHOICES",
        "AnnouncementStatusEnum": (
            "apps.announcements.models.AnnouncementStatus.CHOICES"
        ),
        "ProfileStatusEnum": "apps.accounts.models.Profile.STATUS_CHOICES",
        "TwoFactorVerificationStatusEnum": "apps.two_factor.models.TwoFactorVerification.STATUS_CHOICES",
        "FriendRequestStatusEnum": "apps.social.models.FriendRequest.STATUS_CHOICES",
        "StudyGroupStatusEnum": "apps.social.models.StudyGroup.STATUS_CHOICES",
        "StudyGroupMemberStatusEnum": "apps.social.models.StudyGroupMember.STATUS_CHOICES",
        "UserSemesterEnum": "apps.accounts.models.User.SEMESTER_CHOICES",
        "UnitSemesterEnum": "apps.courses.models.Unit.SEMESTER_CHOICES",
        "UserRoleEnum": "apps.accounts.models.User.ROLE_CHOICES",
        "StudyGroupMemberRoleEnum": "apps.social.models.StudyGroupMember.ROLE_CHOICES",
    },
}

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "debug.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Site Name
SITE_NAME = config("SITE_NAME", default="CampusHub")

# Jazzmin Settings
JAZZMIN_SETTINGS = {
    "site_title": "CampusHub Admin",
    "site_header": "CampusHub Administration",
    "site_brand": "CampusHub",
    "welcome_sign": "Welcome to CampusHub Admin Panel",
    "topbar_links": [
        {"name": "Home", "url": "/", "new_window": True},
        {"name": "Documentation", "url": "/api/docs/", "new_window": True},
    ],
    "user_avatar": "profile_image",
    "show_sidebar": True,
    "show_ui_builder": False,
    "navigation_expanded": True,
    "order_with_respect_to": ["auth", "accounts", "resources", "referrals", "payments"],
    "icons": {
        "accounts.User": "fas fa-users",
        "accounts.Profile": "fas fa-user-circle",
        "faculties.Faculty": "fas fa-university",
        "faculties.Department": "fas fa-building",
        "courses.Course": "fas fa-graduation-cap",
        "courses.Unit": "fas fa-book",
        "resources.Resource": "fas fa-file-alt",
        "bookmarks.Bookmark": "fas fa-bookmark",
        "comments.Comment": "fas fa-comments",
        "ratings.Rating": "fas fa-star",
        "downloads.Download": "fas fa-download",
        "notifications.Notification": "fas fa-bell",
        "moderation.ModerationLog": "fas fa-gavel",
        "referrals.ReferralCode": "fas fa-code",
        "referrals.Referral": "fas fa-user-plus",
        "referrals.RewardTier": "fas fa-trophy",
        "referrals.RewardHistory": "fas fa-history",
        "payments.Plan": "fas fa-credit-card",
        "payments.Subscription": "fas fa-sync",
        "payments.Payment": "fas fa-money-bill",
        "payments.Invoice": "fas fa-file-invoice",
        "payments.PromoCode": "fas fa-tag",
    },
    "custom_links": {
        "payments": [
            {
                "name": "All Payments",
                "url": "/admin/payments/payment/",
                "icon": "fas fa-money-bill-wave",
            },
            {
                "name": "Subscriptions",
                "url": "/admin/payments/subscription/",
                "icon": "fas fa-sync-alt",
            },
            {
                "name": "Plans",
                "url": "/admin/payments/plan/",
                "icon": "fas fa-layer-group",
            },
            {
                "name": "Invoices",
                "url": "/admin/payments/invoice/",
                "icon": "fas fa-receipt",
            },
            {
                "name": "Promo Codes",
                "url": "/admin/payments/promocode/",
                "icon": "fas fa-tag",
            },
        ],
        "referrals": [
            {
                "name": "Referral Codes",
                "url": "/admin/referrals/referralcode/",
                "icon": "fas fa-code",
            },
            {
                "name": "All Referrals",
                "url": "/admin/referrals/referral/",
                "icon": "fas fa-users",
            },
            {
                "name": "Reward Tiers",
                "url": "/admin/referrals/rewardtier/",
                "icon": "fas fa-trophy",
            },
            {
                "name": "Reward History",
                "url": "/admin/referrals/rewardhistory/",
                "icon": "fas fa-history",
            },
        ],
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-success",
    "accent_color": "accent-primary",
    "dark_mode": False,
    "change_form_vars": True,
    "row_overrides": {
        "bg-dark": "bg-dark",
    },
    "block_month": True,
}
