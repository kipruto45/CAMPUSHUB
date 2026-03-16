"""
Sentry configuration for CampusHub.
Provides error tracking and performance monitoring.
"""

import logging
from contextlib import nullcontext
from typing import Any, Dict

try:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    SENTRY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None
    DjangoIntegration = None
    CeleryIntegration = None
    SENTRY_AVAILABLE = False

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """
    Initialize Sentry SDK with Django and Celery integrations.
    Call this from your Django settings.
    """
    from django.conf import settings

    if not SENTRY_AVAILABLE:
        logger.warning("sentry-sdk is not installed, Sentry will not be initialized")
        return

    dsn = getattr(settings, "SENTRY_DSN", None)

    if not dsn:
        logger.warning("SENTRY_DSN not configured, Sentry will not be initialized")
        return

    sentry_sdk.init(
        dsn=dsn,
        # Environment
        environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        # Release tracking
        release=getattr(settings, "SENTRY_RELEASE", "1.0.0"),
        # Performance monitoring
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1),
        # Session tracking
        sessions_sample_rate=getattr(settings, "SENTRY_SESSIONS_SAMPLE_RATE", 0.1),
        # Error monitoring
        error_sample_rate=getattr(settings, "SENTRY_ERROR_SAMPLE_RATE", 1.0),
        # Integrations
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        # Ignore certain errors
        ignore_errors=[
            KeyboardInterrupt,
            SystemExit,
            ConnectionError,
            TimeoutError,
        ],
        # Filter by status code
        before_send=filter_events,
        # Attach user context
        send_default_pii=getattr(settings, "SENTRY_SEND_DEFAULT_PII", False),
        # Request ID for tracking
        request_bodies="medium",
    )

    logger.info(f"Sentry initialized with DSN: {dsn[:20]}...")


def filter_events(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Filter events before sending to Sentry.
    Can be used to customize which errors get reported.
    """
    # Ignore 404 errors for certain paths
    if "request" in event:
        url = event["request"].get("url", "")

        # Don't report health check failures
        if "/health/" in url and event.get("level") == "warning":
            return None

        # Don't report static file 404s
        if "/static/" in url or "/media/" in url:
            return None

    # Don't report certain exception types
    if "exc_info" in hint:
        exc_type = hint["exc_info"][0]

        # Ignore specific exceptions
        ignored_exceptions = [
            "Http404",
            "PermissionDenied",
            "SuspiciousOperation",
        ]

        if exc_type.__name__ in ignored_exceptions:
            return None

    return event


def capture_exception_with_context(
    exc: Exception,
    extra: Dict[str, Any] | None = None,
    user_id: int | None = None,
    request: Any = None,
) -> None:
    """
    Capture an exception with additional context.

    Usage:
        try:
            # Your code
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={'custom_field': 'value'},
                user_id=request.user.id if request else None
            )
    """
    if not SENTRY_AVAILABLE:
        return

    from django.contrib.auth import get_user_model

    User = get_user_model()

    with sentry_sdk.push_scope() as scope:
        # Add extra data
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        # Add user context
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                scope.set_user(
                    {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                    }
                )
            except User.DoesNotExist:
                pass

        # Add request context
        if request:
            scope.set_extra("path", request.path)
            scope.set_extra("method", request.method)

        sentry_sdk.capture_exception(exc)


def capture_message_with_context(
    message: str,
    level: str = "info",
    extra: Dict[str, Any] | None = None,
    user_id: int | None = None,
) -> None:
    """
    Capture a message with additional context.

    Usage:
        capture_message_with_context(
            'User performed action',
            level='info',
            extra={'action': 'download', 'resource_id': 123}
        )
    """
    if not SENTRY_AVAILABLE:
        return

    with sentry_sdk.push_scope() as scope:
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        if user_id:
            scope.set_user({"id": str(user_id)})

        sentry_sdk.capture_message(message, level=level)


class SentryMiddleware:
    """
    Django middleware to capture request errors in Sentry.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Capture exceptions from views."""
        if not SENTRY_AVAILABLE:
            return None

        # Only capture certain exceptions
        if isinstance(exception, (KeyboardInterrupt, SystemExit)):
            return None

        # Add request context
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("path", request.path)
            scope.set_extra("method", request.method)

            if hasattr(request, "user") and request.user.is_authenticated:
                scope.set_user(
                    {
                        "id": request.user.id,
                        "email": request.user.email,
                    }
                )

            sentry_sdk.capture_exception(exception)

        return None


# Celery error tracking
def capture_celery_task_failure(task_id: str, exception: Exception, **kwargs) -> None:
    """
    Capture Celery task failures.
    Use this in your Celery task's error handling.
    """
    if not SENTRY_AVAILABLE:
        return

    with sentry_sdk.push_scope() as scope:
        scope.set_extra("task_id", task_id)
        scope.set_extra("task_kwargs", kwargs)

        sentry_sdk.capture_exception(exception)


# Performance monitoring
def start_transaction(name: str, operation: str = "custom") -> Any:
    """
    Start a performance transaction.

    Usage:
        with start_transaction('my_api_call', 'http'):
            # Your code
            pass
    """
    if not SENTRY_AVAILABLE:
        return nullcontext()

    return sentry_sdk.start_transaction(name=name, op=operation)


# Custom breadcrumbs
def add_breadcrumb(
    category: str, message: str, level: str = "info", data: Dict[str, Any] | None = None
) -> None:
    """
    Add a breadcrumb for tracing user actions.

    Usage:
        add_breadcrumb(
            category='auth',
            message='User logged in',
            level='info',
            data={'user_id': 123}
        )
    """
    if not SENTRY_AVAILABLE:
        return

    sentry_sdk.add_breadcrumb(
        category=category, message=message, level=level, data=data or {}
    )


# Health check integration
def check_sentry_health() -> Dict[str, bool]:
    """
    Check Sentry integration health.
    """
    if not SENTRY_AVAILABLE:
        return {
            "sentry_enabled": False,
            "capturing_events": False,
        }

    try:
        # Try to capture a test event
        sentry_sdk.capture_message("Health check", level="debug")
        return {
            "sentry_enabled": True,
            "capturing_events": True,
        }
    except Exception:
        return {
            "sentry_enabled": False,
            "capturing_events": False,
        }
