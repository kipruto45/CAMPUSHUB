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
    "apps.faculties",
    "apps.courses",
    "apps.resources",
    "apps.bookmarks",
    "apps.comments",
    "apps.ratings",
    "apps.downloads",
    "apps.notifications",
    "apps.search",
    "apps.analytics",
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
    "apps.two_factor",
    "apps.graphql",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
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


def _postgres_database_from_env() -> dict:
    """Build a PostgreSQL DATABASES['default'] entry from DB_* / POSTGRES_* vars."""
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config(
            "DB_NAME",
            default=config("POSTGRES_DB", default="campushub_db"),
        ),
        "USER": config(
            "DB_USER",
            default=config("POSTGRES_USER", default="postgres"),
        ),
        "PASSWORD": config(
            "DB_PASSWORD",
            default=config("POSTGRES_PASSWORD", default=""),
        ),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }


def _should_use_postgres_in_non_production() -> bool:
    engine = config("DB_ENGINE", default="").strip().lower()
    if engine in {"postgres", "postgresql", "pgsql"}:
        return True
    return config(
        "USE_POSTGRES",
        default="false",
        cast=lambda value: str(value).strip().lower() in {"1", "true", "yes", "on"},
    )


def _resolve_default_database(environment: str, database_url: str) -> dict:
    if database_url:
        return _database_from_url(database_url)
    if environment == "production" or _should_use_postgres_in_non_production():
        # Production uses PostgreSQL, and development can opt in via DB_* variables.
        return _postgres_database_from_env()
    # Safe local fallback for developer machines and mobile-integration testing.
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "dev_db.sqlite3",
    }


DATABASE_URL = config("DATABASE_URL", default="").strip()
default_database = _resolve_default_database(ENVIRONMENT, DATABASE_URL)

DATABASES = {
    "default": default_database,
}

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
        "mobile_anon": "60/minute",
        "mobile_auth": "500/hour",
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
    # Long refresh token lifetime (30 days) - user stays logged in until logout
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(config("JWT_REFRESH_TOKEN_LIFETIME", default=30))
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

_cloudinary_credentials_present = bool(
    CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET
)
CLOUDINARY_ENABLED = config(
    "CLOUDINARY_ENABLED",
    default=str(_cloudinary_credentials_present and not DEBUG),
    cast=bool,
)

if CLOUDINARY_ENABLED and _cloudinary_credentials_present:
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "API_KEY": CLOUDINARY_API_KEY,
        "API_SECRET": CLOUDINARY_API_SECRET,
    }

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

# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/0"
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
}

# Cache configuration
CACHE_REDIS_URL = config("REDIS_URL", default="").strip()
CACHE_BACKEND_DEFAULT = (
    "redis" if (ENVIRONMENT == "production" and CACHE_REDIS_URL) else "locmem"
)
CACHE_BACKEND = config(
    "CACHE_BACKEND",
    default=CACHE_BACKEND_DEFAULT,
).strip().lower()

# If redis requested but no URL, fall back to locmem to avoid startup failures
if CACHE_BACKEND == "redis" and not CACHE_REDIS_URL:
    CACHE_BACKEND = "locmem"

if CACHE_BACKEND == "redis":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_REDIS_URL,
        }
    }
elif CACHE_BACKEND == "locmem":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"campushub-{ENVIRONMENT}-cache",
        }
    }
else:
    raise ImproperlyConfigured(
        "CACHE_BACKEND must be either 'redis' or 'locmem'."
    )

# Channels Configuration (WebSockets)
CACHE_REDIS_URL = CACHE_REDIS_URL  # reuse above
CHANNEL_LAYER_BACKEND_DEFAULT = "redis" if CACHE_REDIS_URL else "inmemory"
CHANNEL_LAYER_BACKEND = config(
    "CHANNEL_LAYER_BACKEND", default=CHANNEL_LAYER_BACKEND_DEFAULT
).strip().lower()

# If redis requested but no URL, fall back to inmemory to avoid startup failures
if CHANNEL_LAYER_BACKEND == "redis" and not CACHE_REDIS_URL:
    CHANNEL_LAYER_BACKEND = "inmemory"

if CHANNEL_LAYER_BACKEND == "inmemory":
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CACHE_REDIS_URL],
            },
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
    "order_with_respect_to": ["auth", "accounts", "resources"],
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
