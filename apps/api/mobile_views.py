"""
Mobile API Views for CampusHub.
Provides optimized endpoints for mobile clients with simplified JSON responses.
"""

from __future__ import annotations

from datetime import timedelta
import logging
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import AuthenticationFailed, ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.activity.services import ActivityService
from apps.admin_management.services import get_system_health
from apps.accounts.authentication import (
    JWTAuthentication,
    generate_tokens_for_user,
)
from apps.accounts.constants import EMAIL_NOT_VERIFIED_CODE, EMAIL_NOT_VERIFIED_MESSAGE
from apps.accounts.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from apps.accounts.signals import log_user_activity
from apps.accounts.verification import (
    EmailVerificationToken,
    PasswordResetToken,
    generate_signed_password_reset_token,
    generate_signed_verification_token,
    validate_signed_password_reset_token,
    validate_signed_verification_token,
)
from apps.announcements.models import Announcement, AnnouncementStatus
from apps.api.throttles import (
    MobileAuthenticateThrottle,
    MobileUploadThrottle,
    MobileUserRateThrottle,
)
from apps.bookmarks.models import Bookmark
from apps.bookmarks.services import BookmarkService
from apps.core.idempotency import (
    cache_idempotent_response,
    get_cached_idempotent_response,
)
from apps.core.emails import EmailService, UserEmailService
from apps.courses.models import Course, Unit
from apps.downloads.services import DownloadService
from apps.core.storage.utils import build_storage_download_path
from apps.faculties.models import Faculty, Department
from apps.favorites.models import Favorite, FavoriteType
from apps.favorites.services import FavoriteService
from apps.library.serializers import (
    PersonalFolderSerializer,
    PersonalResourceSerializer,
)
from apps.library.services import (
    get_default_resource_type_folder_name,
    get_storage_summary,
    save_public_resource_to_library,
)
from apps.notifications.fcm import fcm_service
from apps.notifications.models import Notification
from apps.resources.models import PersonalFolder, PersonalResource, Resource
from apps.resources.serializers import (
    ResourceCreateSerializer,
    ResourceSerializer,
    SaveToLibrarySerializer,
)
from apps.resources.services import ResourceDetailService

from .mobile_serializers import MobileDeviceSerializer, MobileUserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class MobileResponse:
    """Helper class for consistent mobile API responses."""

    @staticmethod
    def success(data=None, message=None, request=None, **kwargs):
        response = {
            "success": True,
            "meta": {
                "api_version": str(getattr(settings, "MOBILE_API_VERSION", "1.0"))
            },
        }
        if message:
            response["message"] = message
        if data is not None:
            response["data"] = data
        if request is not None and getattr(request, "request_id", None):
            response["meta"]["request_id"] = request.request_id
        response.update(kwargs)
        return Response(response)

    @staticmethod
    def error(
        message,
        code=None,
        details=None,
        status_code=status.HTTP_400_BAD_REQUEST,
        request=None,
        **kwargs,
    ):
        response = {
            "success": False,
            "error": {"message": message, "code": code or "ERROR"},
            "code": code or "ERROR",
            "detail": message,
            "meta": {
                "api_version": str(getattr(settings, "MOBILE_API_VERSION", "1.0"))
            },
        }
        if details:
            response["error"]["details"] = details
        if request is not None and getattr(request, "request_id", None):
            response["meta"]["request_id"] = request.request_id
        response.update(kwargs)
        return Response(response, status=status_code)


def _parse_positive_int(value, default, max_value=100):
    """Parse positive integer query params with safe bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, max_value))


def _parse_boolean_flag(value) -> bool:
    """Parse booleans from JSON booleans, ints, and common string values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_academic_filter_params(request):
    """Parse optional semester and year-of-study filters from query params."""
    semester = str(request.query_params.get("semester", "") or "").strip()
    if semester and semester not in {"1", "2"}:
        raise DRFValidationError({"semester": "Semester must be 1 or 2."})

    year_raw = request.query_params.get("year_of_study")
    year_of_study = None
    if year_raw not in (None, ""):
        try:
            year_of_study = int(year_raw)
        except (TypeError, ValueError):
            raise DRFValidationError(
                {"year_of_study": "Year of study must be a whole number."}
            )
        if year_of_study < 1:
            raise DRFValidationError(
                {"year_of_study": "Year of study must be at least 1."}
            )

    return semester or None, year_of_study


def _extract_refresh_token(request) -> str:
    """Accept both legacy and mobile refresh token field names."""
    return str(
        request.data.get("refresh_token")
        or request.data.get("refresh")
        or ""
    ).strip()


def _model_table_exists(model_class):
    """Check whether a model table exists in the current database."""
    from django.db import connection

    return model_class._meta.db_table in connection.introspection.table_names()


def _parse_resource_sort(sort_value: str | None) -> list[str]:
    """Map exposed sort keys to deterministic resource ordering."""
    sort_map = {
        "newest": ["-created_at", "-id"],
        "oldest": ["created_at", "id"],
        "popular": ["-download_count", "-view_count", "-created_at", "-id"],
        "downloads": ["-download_count", "-created_at", "-id"],
        "rating": ["-average_rating", "-download_count", "-created_at", "-id"],
        "title": ["title", "-created_at", "-id"],
    }
    key = str(sort_value or "newest").strip().lower()
    return sort_map.get(key, sort_map["newest"])


def _paginate_queryset(
    queryset, request, *, default_limit=20, max_limit=50
) -> tuple[object, dict]:
    """Paginate a queryset for mobile endpoints."""
    page = _parse_positive_int(
        request.query_params.get("page", 1), default=1, max_value=1000
    )
    limit = _parse_positive_int(
        request.query_params.get("limit", default_limit),
        default=default_limit,
        max_value=max_limit,
    )
    offset = (page - 1) * limit
    end = offset + limit
    total = queryset.count()
    return (
        queryset[offset:end],
        {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_register(request):
    """
    Mobile-optimized registration endpoint.
    Accepts: email, password, first_name, last_name, registration_number
    """
    from apps.accounts.serializers import UserRegistrationSerializer

    payload = request.data.copy()
    first_name = str(payload.get("first_name", "") or "").strip()
    last_name = str(payload.get("last_name", "") or "").strip()
    if not payload.get("full_name"):
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if full_name:
            payload["full_name"] = full_name

    if payload.get("password") and not payload.get("password_confirm"):
        payload["password_confirm"] = payload["password"]

    serializer = UserRegistrationSerializer(data=payload)
    if serializer.is_valid():
        user = serializer.save()
        _send_mobile_registration_email(request, user)
        return MobileResponse.success(
            data={
                "user_id": user.id,
                "email": user.email,
                "message": "Registration successful. Please verify your email before logging in.",
                "requires_email_verification": True,
            },
            message="Account created successfully",
        )
    return MobileResponse.error(
        message="Registration failed", details=serializer.errors
    )


# =============================================================================
# Public Academic Data Endpoints (for registration)
# =============================================================================


@api_view(["GET"])
@permission_classes([AllowAny])
def public_faculties(request):
    """
    Get all faculties for public access (registration).
    """
    faculties = Faculty.objects.filter(is_active=True).order_by("name")
    data = {
        "faculties": [
            {"id": f.id, "name": f.name, "code": f.code}
            for f in faculties
        ]
    }
    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_departments(request):
    """
    Get departments by faculty for public access (registration).
    Query params: faculty_id
    """
    faculty_id = request.query_params.get("faculty_id")
    if not faculty_id:
        return MobileResponse.error(message="faculty_id is required")

    try:
        faculty = Faculty.objects.get(id=faculty_id, is_active=True)
    except Faculty.DoesNotExist:
        return MobileResponse.error(message="Faculty not found")

    departments = Department.objects.filter(
        faculty=faculty, is_active=True
    ).order_by("name")

    data = {
        "departments": [
            {"id": d.id, "name": d.name, "code": d.code, "faculty_id": d.faculty_id}
            for d in departments
        ]
    }
    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_courses(request):
    """
    Get courses by department or faculty for public access (registration).
    Query params: department_id OR faculty_id, semester, year_of_study
    """
    department_id = request.query_params.get("department_id")
    faculty_id = request.query_params.get("faculty_id")
    
    if not department_id and not faculty_id:
        return MobileResponse.error(message="department_id or faculty_id is required")

    try:
        semester, year_of_study = _parse_academic_filter_params(request)
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Invalid academic filters",
            details=exc.detail,
        )

    # Get courses by department
    if department_id:
        try:
            department = Department.objects.get(id=department_id, is_active=True)
        except Department.DoesNotExist:
            return MobileResponse.error(message="Department not found")

        courses = Course.objects.filter(department=department, is_active=True)
        if semester:
            courses = courses.filter(units__semester=semester, units__is_active=True)
        if year_of_study is not None:
            courses = courses.filter(
                units__year_of_study=year_of_study,
                units__is_active=True,
            )
    # Get courses by faculty (all departments in the faculty)
    elif faculty_id:
        try:
            faculty = Faculty.objects.get(id=faculty_id, is_active=True)
        except Faculty.DoesNotExist:
            return MobileResponse.error(message="Faculty not found")
        
        # Get all active departments in this faculty
        department_ids = list(Department.objects.filter(
            faculty=faculty, 
            is_active=True
        ).values_list('id', flat=True))
        
        courses = Course.objects.filter(department_id__in=department_ids, is_active=True)
        if semester:
            courses = courses.filter(units__semester=semester, units__is_active=True)
        if year_of_study is not None:
            courses = courses.filter(
                units__year_of_study=year_of_study,
                units__is_active=True,
            )
    
    courses = courses.distinct().order_by("name")

    data = {
        "courses": [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "department_id": c.department_id,
                "duration_years": c.duration_years,
            }
            for c in courses
        ]
    }
    return MobileResponse.success(data=data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_login(request):
    """
    Mobile-optimized login endpoint.
    Accepts: email OR registration_number, password, device_token
    Returns: access_token, refresh_token, user data with role
    """
    from apps.accounts.serializers import LoginSerializer

    payload = request.data.copy()
    # Support both email and registration_number directly
    serializer = LoginSerializer(data=payload, context={"request": request})
    try:
        serializer.is_valid(raise_exception=True)
    except AuthenticationFailed as exc:
        error_code = exc.get_codes() if hasattr(exc, "get_codes") else None
        code = error_code if isinstance(error_code, str) else "AUTH_FAILED"
        return MobileResponse.error(
            message=str(exc.detail),
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            request=request,
        )
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Login failed",
            details=exc.detail,
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )

    user = serializer.validated_data["user"]
    if not user.is_verified:
        return MobileResponse.error(
            message=EMAIL_NOT_VERIFIED_MESSAGE,
            code=EMAIL_NOT_VERIFIED_CODE,
            status_code=status.HTTP_403_FORBIDDEN,
            request=request,
        )

    try:
        from apps.payments.freemium import ensure_default_trial

        ensure_default_trial(user, source="mobile_login")
    except Exception:
        logger.exception("Failed to auto-provision mobile trial for user_id=%s", user.id)

    remember_me = _parse_boolean_flag(payload.get("remember_me", True))
    tokens = generate_tokens_for_user(user, remember_me=remember_me)
    user.update_last_login()

    try:
        from apps.accounts.services import register_user_session

        register_user_session(user, request, tokens.get("refresh"))
    except Exception:
        logger.exception("Failed to register mobile session for user_id=%s", user.id)

    from apps.accounts.views import _is_suspicious_login, _send_suspicious_login_alert
    try:
        from apps.gamification.services import GamificationService

        GamificationService.record_login(user)
    except Exception:
        logger.exception(
            "Failed to record mobile login gamification for user_id=%s",
            user.id,
        )

    if _is_suspicious_login(user, request):
        _send_suspicious_login_alert(user, request)

    log_user_activity(user, "login", "User logged in via mobile API", request)

    # Save device token if provided
    device_token = payload.get("device_token")
    if device_token:
        _save_device_token(
            user, device_token, payload.get("device_type", "android")
        )

    user_data = MobileUserSerializer(user).data

    return MobileResponse.success(
        data={
            "access_token": tokens["access"],
            "refresh_token": tokens["refresh"],
            "expires_in": 3600,  # 1 hour
            "remember_me": remember_me,
            "user": user_data,
        }
    )
    return MobileResponse.error(message="Login failed", request=request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_logout(request):
    """Mobile logout endpoint - invalidates device token."""
    refresh_token = _extract_refresh_token(request)
    if refresh_token:
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            outstanding = OutstandingToken.objects.filter(token=refresh_token).first()
            if outstanding:
                BlacklistedToken.objects.get_or_create(token=outstanding)
            else:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            logger.exception("Failed to blacklist mobile logout token")

        try:
            from apps.accounts.services import deactivate_user_session

            deactivate_user_session(request.user, refresh_token)
        except Exception:
            logger.exception("Failed to deactivate mobile session for user_id=%s", request.user.id)

    device_token = request.data.get("device_token")
    if device_token:
        _remove_device_token(request.user, device_token)

    log_user_activity(request.user, "logout", "User logged out via mobile API", request)
    return MobileResponse.success(message="Logged out successfully")


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_refresh_token(request):
    """Refresh access token."""
    refresh_token = _extract_refresh_token(request)
    if not refresh_token:
        return MobileResponse.error(
            message="Refresh token required", code="MISSING_REFRESH_TOKEN"
        )

    try:
        refresh = RefreshToken(refresh_token)
        user_id = refresh.get("user_id")
        if not user_id:
            raise TokenError("Token contained no user_id claim")

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            return MobileResponse.error(
                message="User not found or inactive",
                code="INVALID_REFRESH_TOKEN",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        refresh.blacklist()
        next_refresh = RefreshToken.for_user(user)
        try:
            from apps.accounts.services import register_user_session

            register_user_session(user, request, str(next_refresh))
        except Exception:
            logger.exception("Failed to refresh session tracking for user_id=%s", user.id)
        return MobileResponse.success(
            data={
                "access_token": str(next_refresh.access_token),
                "refresh_token": str(next_refresh),
                "expires_in": 3600,
            }
        )
    except TokenError:
        return MobileResponse.error(
            message="Invalid or expired refresh token",
            code="INVALID_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_password_reset_request(request):
    """Mobile-friendly password reset request endpoint."""
    from apps.accounts.views import (
        _build_mobile_deeplink,
        _build_password_reset_link,
        _send_template_email_with_fallback,
    )

    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return MobileResponse.error(
            message="Password reset request failed",
            code="PASSWORD_RESET_REQUEST_FAILED",
            details=serializer.errors,
        )

    email = serializer.validated_data["email"].strip().lower()
    user = User.objects.filter(email=email, is_active=True).first()
    if user:
        token = generate_signed_password_reset_token(user)
        reset_url = _build_mobile_deeplink("reset-password", {"token": token})
        if not reset_url:
            reset_url = _build_password_reset_link(request, token)
        sent = _send_template_email_with_fallback(
            subject="CampusHub password reset",
            template_name="password_reset",
            context={
                "user": user,
                "reset_url": reset_url,
                "site_name": getattr(settings, "SITE_NAME", "CampusHub"),
                "reset_link_expires_hours": 1,
            },
            fallback_message=(
                "Use this link to reset your password:\n"
                f"{reset_url}\n\nThis link expires in 1 hour."
            ),
            recipient_email=user.email,
        )
        if not sent:
            logger.error(
                "Mobile password reset email delivery failed for user_id=%s email=%s",
                user.id,
                user.email,
            )

    return MobileResponse.success(
        message="Password reset email sent.",
        data={"email": email},
        request=request,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_password_reset_confirm(request, token):
    """Mobile-friendly password reset confirmation endpoint."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return MobileResponse.error(
            message="Password reset failed",
            code="PASSWORD_RESET_CONFIRM_FAILED",
            details=serializer.errors,
        )

    user = validate_signed_password_reset_token(token)
    if not user and _model_table_exists(PasswordResetToken):
        reset_token = (
            PasswordResetToken.objects.select_related("user")
            .filter(token=token)
            .first()
        )
        if reset_token and reset_token.is_valid():
            user = reset_token.user
            reset_token.is_used = True
            reset_token.save(update_fields=["is_used"])

    if not user:
        return MobileResponse.error(
            message="Invalid or expired reset token.",
            code="INVALID_RESET_TOKEN",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password", "updated_at"])

    return MobileResponse.success(
        message="Password reset successful.",
        data={"email": user.email},
        request=request,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def mobile_verify_email(request, token):
    """Mobile-friendly email verification endpoint."""
    user = validate_signed_verification_token(token)
    if not user and _model_table_exists(EmailVerificationToken):
        verify_token = (
            EmailVerificationToken.objects.select_related("user")
            .filter(token=token)
            .first()
        )
        if verify_token and verify_token.is_valid():
            user = verify_token.user
            verify_token.is_used = True
            verify_token.save(update_fields=["is_used"])

    if not user:
        return MobileResponse.error(
            message="Invalid or expired verification token.",
            code="INVALID_VERIFICATION_TOKEN",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])
        try:
            from apps.gamification.services import GamificationService

            GamificationService.record_email_verification(user)
        except Exception:
            logger.exception(
                "Failed to record mobile email verification gamification for user_id=%s",
                user.id,
            )

    return MobileResponse.success(
        message="Email verified successfully.",
        data={"email": user.email, "is_verified": True},
        request=request,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MobileAuthenticateThrottle])
def mobile_resend_verification_email(request):
    """Mobile-friendly resend verification endpoint."""
    from apps.accounts.views import _send_account_verification_email

    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return MobileResponse.error(
            message="Email is required.",
            code="MISSING_EMAIL",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.filter(email=email, is_active=True).first()
    if user and not user.is_verified:
        try:
            _send_account_verification_email(request, user, welcome=False)
        except Exception:
            logger.exception(
                "Failed to resend mobile verification email for %s", user.email
            )

    return MobileResponse.success(
        message="If that account exists, a verification email has been sent.",
        data={"email": email},
        request=request,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_dashboard(request):
    """Get dashboard data optimized for mobile."""
    user = request.user

    # Get stats
    total_uploads = Resource.objects.filter(uploaded_by=user).count()
    total_downloads = user.downloads.count() if hasattr(user, "downloads") else 0
    total_bookmarks = Bookmark.objects.filter(user=user).count()
    total_favorites = Favorite.objects.filter(user=user).count()

    # Recent resources
    recent_resources = (
        Resource.objects.filter(status="approved")
        .select_related("uploaded_by", "course", "unit")
        .order_by("-created_at")[:10]
    )

    announcements = _get_cached_announcements(limit=5)

    data = {
        "stats": {
            "total_uploads": total_uploads,
            "total_downloads": total_downloads,
            "total_bookmarks": total_bookmarks,
            "total_favorites": total_favorites,
        },
        "recent_resources": _serialize_resources(recent_resources),
        "announcements": announcements,
    }

    return MobileResponse.success(data=data)


@extend_schema(operation_id="api_mobile_resources_list")
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_resources(request):
    """
    Get resources list with optional filtering.
    Query params: type, faculty, department, course, unit, semester, year_of_study,
    page, limit, search, scope
    """
    # Get scope parameter
    scope = request.query_params.get("scope", "all")
    
    if scope == "my":
        # Show only user's uploaded resources
        resources = Resource.objects.filter(uploaded_by=request.user)
    else:
        resources = Resource.objects.filter(status="approved")

    # Apply filters
    resource_type = request.query_params.get("type")
    if resource_type:
        resources = resources.filter(resource_type=resource_type)

    faculty_id = request.query_params.get("faculty")
    if faculty_id:
        resources = resources.filter(faculty_id=faculty_id)

    department_id = request.query_params.get("department")
    if department_id:
        resources = resources.filter(department_id=department_id)

    course_id = request.query_params.get("course")
    if course_id:
        resources = resources.filter(course_id=course_id)

    unit_id = request.query_params.get("unit")
    if unit_id:
        resources = resources.filter(unit_id=unit_id)

    try:
        semester, year_of_study = _parse_academic_filter_params(request)
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Invalid academic filters",
            details=exc.detail,
            request=request,
        )

    if semester:
        resources = resources.filter(semester=semester)

    if year_of_study is not None:
        resources = resources.filter(year_of_study=year_of_study)

    search = (request.query_params.get("search") or "").strip()
    if search:
        resources = resources.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(tags__icontains=search)
        )

    sort = request.query_params.get("sort") or request.query_params.get("ordering")
    ordering = _parse_resource_sort(sort)

    resources, pagination = _paginate_queryset(
        resources.select_related("uploaded_by", "faculty", "department", "course", "unit").order_by(*ordering),
        request,
        default_limit=20,
        max_limit=50,
    )

    return MobileResponse.success(
        data={
            "resources": _serialize_resources(resources),
            "pagination": pagination,
            "sort": (sort or "newest"),
        },
        request=request,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUploadThrottle])
def mobile_upload_resource(request):
    """Upload a new public resource from mobile."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    serializer = ResourceCreateSerializer(
        data=request.data, context={"request": request, "is_mobile": True}
    )
    if not serializer.is_valid():
        return MobileResponse.error(
            message="Upload validation failed",
            code="VALIDATION_ERROR",
            details=serializer.errors,
            request=request,
        )

    try:
        resource = serializer.save()
    except (DRFValidationError, DjangoValidationError) as exc:
        detail = (
            exc.detail
            if hasattr(exc, "detail")
            else (
                getattr(exc, "message_dict", None)
                or getattr(exc, "messages", None)
                or str(exc)
            )
        )
        return MobileResponse.error(
            message="Upload failed",
            code="UPLOAD_FAILED",
            details=detail,
            request=request,
        )

    if resource.status != "pending":
        resource.status = "pending"
        resource.save(update_fields=["status", "updated_at"])

    response = MobileResponse.success(
        data={
            "resource": ResourceSerializer(resource, context={"request": request}).data,
            "status": resource.status,
        },
        message="Resource uploaded and submitted for review.",
        request=request,
    )
    return cache_idempotent_response(request, response)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_bookmarks(request):
    """Get bookmarked resources for the current user."""
    params = request.query_params
    queryset = BookmarkService.get_user_bookmarks(
        request.user,
        resource_type=params.get("resource_type"),
        course_id=params.get("course"),
        unit_id=params.get("unit"),
        sort=params.get("sort", "newest"),
    ).select_related("resource", "resource__course", "resource__unit")

    bookmarks, pagination = _paginate_queryset(
        queryset, request, default_limit=20, max_limit=50
    )

    data = {
        "bookmarks": [
            {
                "id": bookmark.id,
                "saved_at": bookmark.created_at.isoformat(),
                "resource": (
                    _serialize_resources([bookmark.resource])[0]
                    if bookmark.resource
                    else None
                ),
            }
            for bookmark in bookmarks
        ],
        "pagination": pagination,
    }
    return MobileResponse.success(data=data, request=request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_favorites(request):
    """Get favorites for the current user."""
    type_param = str(request.query_params.get("type", "")).strip().lower()
    type_aliases = {
        "resources": FavoriteType.RESOURCE,
        "resource": FavoriteType.RESOURCE,
        "files": FavoriteType.PERSONAL_FILE,
        "file": FavoriteType.PERSONAL_FILE,
        "folders": FavoriteType.FOLDER,
        "folder": FavoriteType.FOLDER,
    }
    favorite_type = type_aliases.get(type_param)

    queryset = FavoriteService.get_user_favorites(
        request.user, favorite_type=favorite_type
    ).select_related(
        "resource",
        "resource__course",
        "resource__unit",
        "personal_file",
        "personal_folder",
    )

    favorites, pagination = _paginate_queryset(
        queryset, request, default_limit=20, max_limit=50
    )

    data = {
        "favorites": [],
        "pagination": pagination,
    }

    for favorite in favorites:
        item = {
            "id": favorite.id,
            "saved_at": favorite.created_at.isoformat(),
            "favorite_type": favorite.favorite_type,
            "resource": None,
            "personal_file": None,
            "personal_folder": None,
        }
        if favorite.resource:
            item["resource"] = _serialize_resources([favorite.resource])[0]
        elif favorite.personal_file:
            item["personal_file"] = PersonalResourceSerializer(
                favorite.personal_file, context={"request": request}
            ).data
        elif favorite.personal_folder:
            item["personal_folder"] = PersonalFolderSerializer(
                favorite.personal_folder, context={"request": request}
            ).data
        data["favorites"].append(item)

    return MobileResponse.success(data=data, request=request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_toggle_bookmark(request, resource_id):
    """Toggle bookmark state for a resource."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return MobileResponse.error(
            message="Resource not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            request=request,
        )

    try:
        result = BookmarkService.toggle_bookmark(request.user, resource)
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Bookmark request failed",
            code="BOOKMARK_NOT_ALLOWED",
            details=exc.detail if hasattr(exc, "detail") else str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )

    response = MobileResponse.success(data=result, request=request)
    return cache_idempotent_response(request, response)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_toggle_favorite(request, resource_id):
    """Toggle favorite state for a resource."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return MobileResponse.error(
            message="Resource not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            request=request,
        )

    try:
        result = FavoriteService.toggle_favorite(
            user=request.user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Favorite request failed",
            code="FAVORITE_NOT_ALLOWED",
            details=exc.detail if hasattr(exc, "detail") else str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )
    response = MobileResponse.success(data=result, request=request)
    return cache_idempotent_response(request, response)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_download_resource(request, resource_id):
    """Record a resource download and return a mobile-safe payload."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    try:
        resource = Resource.objects.get(id=resource_id, status="approved")
    except Resource.DoesNotExist:
        return MobileResponse.error(
            message="Resource not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            request=request,
        )

    try:
        result = DownloadService.download_public_resource(
            request.user, resource, request
        )
        ActivityService.log_download(
            user=request.user, resource=resource, request=request
        )
    except ValueError as exc:
        # Legacy compatibility: some clients/tests request download metadata for
        # resources without attached files just to obtain directory/header info.
        if str(exc) == "File not available":
            result = {
                "download_id": None,
                "resource_title": resource.title,
                "file_name": "",
                "file_url": "",
            }
        else:
            return MobileResponse.error(
                message=str(exc),
                code="DOWNLOAD_FAILED",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
    except PermissionError as exc:
        return MobileResponse.error(
            message=str(exc),
            code="DOWNLOAD_FAILED",
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )

    file_url = result.get("file_url") or ""
    response = MobileResponse.success(
        data={
            "download_id": result["download_id"],
            "resource_id": resource.id,
            "resource_title": result["resource_title"],
            "file_name": result["file_name"],
            "file_url": request.build_absolute_uri(file_url) if file_url else "",
            "download_directory": getattr(settings, "DOWNLOAD_DIRECTORY", "CampusHub/Downloads"),
            "download_to_app_directory": getattr(settings, "DOWNLOAD_TO_APP_DIRECTORY", True),
            "prevent_system_downloads": getattr(settings, "PREVENT_SYSTEM_DOWNLOADS", True),
        },
        request=request,
    )
    response["X-Download-Directory"] = getattr(settings, "DOWNLOAD_DIRECTORY", "CampusHub/Downloads")
    response["X-Prevent-System-Downloads"] = str(getattr(settings, "PREVENT_SYSTEM_DOWNLOADS", True)).lower()
    return cache_idempotent_response(request, response)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_save_to_library(request, resource_id):
    """Save an approved public resource to user's personal library."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    serializer = SaveToLibrarySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        resource = Resource.objects.get(
            id=resource_id,
            status="approved",
            is_public=True,
        )
    except Resource.DoesNotExist:
        return MobileResponse.error(
            message="Resource not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            request=request,
        )

    folder = None
    folder_id = serializer.validated_data.get("folder_id")
    if folder_id:
        try:
            folder = PersonalFolder.objects.get(id=folder_id, user=request.user)
        except PersonalFolder.DoesNotExist:
            return MobileResponse.error(
                message="Folder not found",
                code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request,
            )

    try:
        personal, created, target_folder = save_public_resource_to_library(
            user=request.user,
            resource=resource,
            folder=folder,
            title=serializer.validated_data.get("title"),
        )
    except ValueError as exc:
        return MobileResponse.error(
            message=str(exc),
            code="SAVE_FAILED",
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )

    response = MobileResponse.success(
        data={
            "item": PersonalResourceSerializer(
                personal, context={"request": request}
            ).data,
            "already_saved": not created,
            "folder": (
                PersonalFolderSerializer(
                    target_folder,
                    context={"request": request},
                ).data
                if target_folder
                else None
            ),
        },
        message=(
            "Resource added to library."
            if created
            else "Resource already exists in your library."
        ),
        request=request,
    )
    return cache_idempotent_response(request, response)


@extend_schema(operation_id="api_mobile_resource_detail_retrieve")
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_resource_detail(request, resource_id):
    """Get single resource details."""
    try:
        resource = Resource.objects.select_related(
            "uploaded_by", "course", "unit", "faculty"
        ).get(id=resource_id, status="approved")

        ResourceDetailService(resource, request.user, request).track_view()

        from apps.favorites.models import Favorite, FavoriteType
        from apps.ratings.models import Rating
        from apps.resources.services import calculate_auto_rating

        likes_count = Favorite.objects.filter(
            resource=resource, favorite_type=FavoriteType.RESOURCE
        ).count()
        ratings_count = Rating.objects.filter(resource=resource).count()
        saved_library_item = (
            PersonalResource.objects.select_related("folder")
            .filter(user=request.user, linked_public_resource=resource)
            .first()
        )
        auto_rating = calculate_auto_rating(
            resource,
            ratings_count=ratings_count,
            likes_count=likes_count,
        )

        data = {
            "id": resource.id,
            "title": resource.title,
            "description": resource.description,
            "resource_type": resource.resource_type,
            "file_type": resource.file_type,
            "file_size": resource.file_size,
            "thumbnail": (
                request.build_absolute_uri(resource.thumbnail.url)
                if resource.thumbnail
                else None
            ),
            "file_url": (
                request.build_absolute_uri(
                    build_storage_download_path(resource.file.name, public=True)
                )
                if resource.file
                else None
            ),
            "uploaded_by": resource.uploaded_by.get_full_name(),
            "course_name": resource.course.name if resource.course else None,
            "unit_name": resource.unit.name if resource.unit else None,
            "download_count": resource.download_count,
            "view_count": resource.view_count,
            "average_rating": float(resource.average_rating or 0),
            "auto_rating": auto_rating,
            "ratings_count": ratings_count,
            "created_at": resource.created_at.isoformat(),
            "is_in_my_library": saved_library_item is not None,
            "default_library_folder_name": get_default_resource_type_folder_name(
                resource.resource_type
            ),
            "library_folder_name": (
                saved_library_item.folder.name
                if saved_library_item and saved_library_item.folder
                else None
            ),
            "is_bookmarked": Bookmark.objects.filter(
                user=request.user, resource=resource
            ).exists(),
            "is_favorited": Favorite.objects.filter(
                user=request.user,
                favorite_type="resource",
                resource=resource,
            ).exists(),
        }

        return MobileResponse.success(data=data)
    except Resource.DoesNotExist:
        return MobileResponse.error(
            message="Resource not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_notifications(request):
    """Get user notifications."""
    cache_key = _notification_cache_key(request, request.user)
    cached = cache.get(cache_key)
    if cached is not None:
        return MobileResponse.success(data=cached, request=request)

    notifications = (
        Notification.objects.filter(recipient=request.user)
        .only(
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "link",
            "target_resource_id",
            "created_at",
        )
    )

    # Unread count
    unread_count = notifications.filter(is_read=False).count()

    notifications, pagination = _paginate_queryset(
        notifications.order_by("-created_at"),
        request,
        default_limit=20,
        max_limit=100,
    )

    data = {
        "notifications": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "notification_type_display": n.notification_type_display,
                "is_read": n.is_read,
                "link": n.link,
                "resource_id": str(n.target_resource_id) if n.target_resource_id else "",
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "unread_count": unread_count,
        "pagination": pagination,
    }

    cache.set(cache_key, data, 15)
    _register_notification_cache_key(request.user.id, cache_key)
    return MobileResponse.success(data=data, request=request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_mark_notification_read(request, notification_id):
    """Mark notification as read."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    try:
        notification = Notification.objects.get(
            id=notification_id, recipient=request.user
        )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])
        _clear_notification_cache(request.user.id)
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        response = MobileResponse.success(
            data={"updated": True, "is_read": True, "unread_count": unread_count},
            message="Notification marked as read",
            request=request,
        )
        return cache_idempotent_response(request, response)
    except Notification.DoesNotExist:
        return MobileResponse.error(
            message="Notification not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_mark_all_notifications_read(request):
    """Mark all user notifications as read."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    mark_qs = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    )
    updated_count = mark_qs.count()
    if updated_count:
        mark_qs.update(is_read=True, updated_at=timezone.now())
    _clear_notification_cache(request.user.id)
    
    # Get current unread count after marking as read
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    
    response = MobileResponse.success(
        data={"updated_count": updated_count, "unread_count": unread_count},
        message="All unread notifications marked as read",
        request=request,
    )
    return cache_idempotent_response(request, response)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_register_device(request):
    """Register device for push notifications."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    serializer = MobileDeviceSerializer(data=request.data)
    if serializer.is_valid():
        _save_device_token(
            request.user,
            serializer.validated_data["device_token"],
            serializer.validated_data.get("device_type", "android"),
            serializer.validated_data.get("device_name"),
            serializer.validated_data.get("device_model"),
            serializer.validated_data.get("app_version"),
        )
        response = MobileResponse.success(message="Device registered", request=request)
        return cache_idempotent_response(request, response)
    return MobileResponse.error(
        message="Device registration failed",
        details=serializer.errors,
        request=request,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_courses(request):
    """Get all courses for mobile."""
    courses = Course.objects.filter(is_active=True).only("id", "name", "code")

    data = {"courses": [{"id": c.id, "name": c.name, "code": c.code} for c in courses]}
    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_units(request, course_id):
    """Get units for a specific course."""
    try:
        semester, year_of_study = _parse_academic_filter_params(request)
    except DRFValidationError as exc:
        return MobileResponse.error(
            message="Invalid academic filters",
            details=exc.detail,
        )

    units = Unit.objects.filter(course_id=course_id, is_active=True)
    if semester:
        units = units.filter(semester=semester)
    if year_of_study is not None:
        units = units.filter(year_of_study=year_of_study)
    units = units.only("id", "name", "code", "semester", "year_of_study")

    data = {
        "units": [
            {
                "id": u.id,
                "name": u.name,
                "code": u.code,
                "semester": u.semester,
                "year_of_study": u.year_of_study,
            }
            for u in units
        ]
    }
    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_faculties(request):
    """Get all faculties for mobile."""
    faculties = Faculty.objects.filter(is_active=True).only("id", "name")

    data = {"faculties": [{"id": f.id, "name": f.name} for f in faculties]}
    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_sync(request):
    """
    Offline sync endpoint - returns data needed for offline caching.
    Returns: recent resources, bookmarks, favorites, user data
    """
    user = request.user

    # Get last sync time
    _ = request.query_params.get("since")

    # User data
    user_data = MobileUserSerializer(user).data

    # Bookmarks
    bookmarks = Bookmark.objects.filter(user=user).select_related("resource")[:50]
    bookmarked_resources = [b.resource_id for b in bookmarks]

    # Favorites
    favorites = Favorite.objects.filter(
        user=user,
        favorite_type="resource",
        resource__isnull=False,
    ).select_related("resource")[:50]
    favorite_resources = [f.resource_id for f in favorites]

    # Recent approved resources (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_resources = Resource.objects.filter(
        status="approved", created_at__gte=week_ago
    ).select_related("uploaded_by", "course", "unit")[:100]

    data = {
        "user": user_data,
        "bookmarked_resources": bookmarked_resources,
        "favorite_resources": favorite_resources,
        "recent_resources": _serialize_resources(recent_resources),
        "sync_timestamp": timezone.now().isoformat(),
    }

    return MobileResponse.success(data=data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_library_summary(request):
    """Get personal library summary for mobile dashboard widgets."""
    summary = get_storage_summary(request.user)
    summary["total_folders"] = PersonalFolder.objects.filter(user=request.user).count()
    summary["trashed_files"] = PersonalResource.all_objects.filter(
        user=request.user, is_deleted=True
    ).count()
    return MobileResponse.success(data={"summary": summary}, request=request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_download_config(request):
    """
    Get mobile download configuration settings.
    
    Returns configuration for where and how files should be downloaded:
    - download_directory: The directory path for downloaded files
    - download_to_app_directory: Whether to save to app's private directory
    - prevent_system_downloads: Whether to prevent appearing in system downloads
    """
    from django.conf import settings
    
    config = {
        "download_directory": getattr(settings, "DOWNLOAD_DIRECTORY", "CampusHub/Downloads"),
        "download_to_app_directory": getattr(settings, "DOWNLOAD_TO_APP_DIRECTORY", True),
        "prevent_system_downloads": getattr(settings, "PREVENT_SYSTEM_DOWNLOADS", True),
    }
    return MobileResponse.success(
        data={"download_config": config},
        download_config=config,
        request=request,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_library_files(request):
    """List personal library files for mobile."""
    queryset = PersonalResource.objects.filter(user=request.user).select_related(
        "folder"
    )

    folder_id = request.query_params.get("folder")
    if folder_id:
        queryset = queryset.filter(folder_id=folder_id)

    search = (request.query_params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(tags__icontains=search)
        )

    queryset = queryset.order_by("-last_accessed_at", "-created_at")
    files, pagination = _paginate_queryset(
        queryset, request, default_limit=20, max_limit=50
    )
    data = {
        "files": PersonalResourceSerializer(
            files, many=True, context={"request": request}
        ).data,
        "pagination": pagination,
    }
    return MobileResponse.success(data=data, request=request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_library_folders(request):
    """List personal folders for mobile."""
    queryset = PersonalFolder.objects.filter(user=request.user)

    parent_id = request.query_params.get("parent")
    if not parent_id or str(parent_id).lower() == "root":
        queryset = queryset.filter(parent__isnull=True)
    else:
        queryset = queryset.filter(parent_id=parent_id)

    queryset = queryset.order_by("-is_favorite", "name")
    folders, pagination = _paginate_queryset(
        queryset, request, default_limit=20, max_limit=50
    )
    data = {
        "folders": PersonalFolderSerializer(folders, many=True).data,
        "pagination": pagination,
    }
    return MobileResponse.success(data=data, request=request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_stats(request):
    """Get user statistics for mobile."""
    from django.conf import settings
    from apps.resources.models import PersonalResource
    
    user = request.user
    
    # Get actual storage usage from personal resources
    storage_used = 0
    personal_files = PersonalResource.objects.filter(user=user, is_deleted=False)
    for pf in personal_files:
        if pf.file and pf.file.size:
            storage_used += pf.file.size
    
    # Get storage limit from user profile or default
    storage_limit = getattr(user, 'storage_limit', None)
    if not storage_limit:
        storage_limit = getattr(settings, 'DEFAULT_STORAGE_LIMIT_MB', 100) * 1024 * 1024
    
    stats = {
        "total_uploads": Resource.objects.filter(uploaded_by=user).count(),
        "total_downloads": user.downloads.count() if hasattr(user, "downloads") else 0,
        "total_bookmarks": Bookmark.objects.filter(user=user).count(),
        "total_favorites": Favorite.objects.filter(user=user).count(),
        "storage_used": storage_used,
        "storage_limit": storage_limit,
    }

    return MobileResponse.success(data={"stats": stats})


# Helper functions


def _serialize_resources(resources):
    """Serialize resources for mobile response."""
    resource_list = list(resources)
    resource_ids = [r.id for r in resource_list]

    likes_map = {}
    ratings_map = {}
    if resource_ids:
        try:
            from apps.favorites.models import Favorite, FavoriteType
            from apps.ratings.models import Rating

            likes_map = {
                row["resource"]: row["count"]
                for row in Favorite.objects.filter(
                    resource_id__in=resource_ids,
                    favorite_type=FavoriteType.RESOURCE,
                )
                .values("resource")
                .annotate(count=models.Count("id"))
            }
            ratings_map = {
                row["resource"]: row["count"]
                for row in Rating.objects.filter(resource_id__in=resource_ids)
                .values("resource")
                .annotate(count=models.Count("id"))
            }
        except Exception:
            likes_map = {}
            ratings_map = {}

    from apps.resources.services import calculate_auto_rating

    return [
        {
            "id": r.id,
            "title": r.title,
            "description": (
                r.description[:100] + "..."
                if r.description and len(r.description) > 100
                else r.description
            ),
            "file_type": r.file_type or r.resource_type,
            "file_size": r.file_size,
            "thumbnail": r.thumbnail.url if r.thumbnail else None,
            "uploaded_by": (
                r.uploaded_by.get_full_name() if r.uploaded_by else "Unknown"
            ),
            "course_name": r.course.name if r.course else None,
            "unit_name": r.unit.name if r.unit else None,
            "download_count": r.download_count,
            "view_count": r.view_count,
            "average_rating": float(r.average_rating or 0),
            "auto_rating": calculate_auto_rating(
                r,
                ratings_count=ratings_map.get(r.id, 0),
                likes_count=likes_map.get(r.id, 0),
            ),
            "ratings_count": ratings_map.get(r.id, 0),
            "created_at": r.created_at.isoformat(),
        }
        for r in resource_list
    ]


def _serialize_announcements(announcements):
    """Serialize announcements for mobile response."""
    return [
        {
            "id": a.id,
            "title": a.title,
            "message": (
                a.content[:150] + "..."
                if a.content and len(a.content) > 150
                else a.content
            ),
            "type": a.announcement_type,
            "created_at": a.created_at.isoformat(),
        }
        for a in announcements
    ]


def _get_cached_announcements(limit=5):
    cache_key = f"mobile:announcements:published:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    queryset = Announcement.objects.filter(
        status=AnnouncementStatus.PUBLISHED
    ).order_by("-is_pinned", "-published_at", "-created_at")[:limit]
    data = _serialize_announcements(queryset)
    cache.set(cache_key, data, 120)
    return data


def _notification_cache_key(request, user):
    return f"mobile:notifications:{user.id}:{request.get_full_path()}"


def _register_notification_cache_key(user_id, key):
    index_key = f"mobile:notifications:keys:{user_id}"
    keys = cache.get(index_key) or []
    if key not in keys:
        keys.append(key)
    cache.set(index_key, keys, 300)


def _clear_notification_cache(user_id):
    index_key = f"mobile:notifications:keys:{user_id}"
    keys = cache.get(index_key) or []
    for key in keys:
        cache.delete(key)
    cache.delete(index_key)


def _save_device_token(
    user, token, device_type, device_name=None, device_model=None, app_version=None
):
    """Save device token for push notifications."""
    from django.db import connection
    from apps.notifications.models import DeviceToken

    if connection.vendor == "sqlite":
        table_name = DeviceToken._meta.db_table
        now = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({table_name})")
            table_info = cursor.fetchall()
        id_column = next((row for row in table_info if row[1] == "id"), None)
        id_decl = str(id_column[2]).upper() if id_column else ""
        is_integer_id = "INT" in id_decl

        if is_integer_id:
            # Legacy sqlite schemas may still use integer PKs for this model.
            sql = (
                f'INSERT INTO "{table_name}" '
                '("created_at", "updated_at", "user_id", "device_token", '
                '"device_type", "device_name", "device_model", "app_version", '
                '"is_active", "last_used") '
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                'ON CONFLICT("device_token") DO UPDATE SET '
                '"updated_at"=excluded."updated_at", '
                '"user_id"=excluded."user_id", '
                '"device_type"=excluded."device_type", '
                '"device_name"=excluded."device_name", '
                '"device_model"=excluded."device_model", '
                '"app_version"=excluded."app_version", '
                '"is_active"=excluded."is_active", '
                '"last_used"=excluded."last_used"'
            )
            params = [
                now,
                now,
                user.id,
                token,
                device_type,
                device_name or "",
                device_model or "",
                app_version or "",
                True,
                now,
            ]
        else:
            sql = (
                f'INSERT INTO "{table_name}" '
                '("id", "created_at", "updated_at", "user_id", "device_token", '
                '"device_type", "device_name", "device_model", "app_version", '
                '"is_active", "last_used") '
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                'ON CONFLICT("device_token") DO UPDATE SET '
                '"updated_at"=excluded."updated_at", '
                '"user_id"=excluded."user_id", '
                '"device_type"=excluded."device_type", '
                '"device_name"=excluded."device_name", '
                '"device_model"=excluded."device_model", '
                '"app_version"=excluded."app_version", '
                '"is_active"=excluded."is_active", '
                '"last_used"=excluded."last_used"'
            )
            params = [
                uuid.uuid4().hex,
                now,
                now,
                user.id,
                token,
                device_type,
                device_name or "",
                device_model or "",
                app_version or "",
                True,
                now,
            ]

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
        return

    DeviceToken.objects.update_or_create(
        device_token=token,
        defaults={
            "user": user,
            "device_type": device_type,
            "device_name": device_name or "",
            "device_model": device_model or "",
            "app_version": app_version or "",
            "is_active": True,
        },
    )


def _remove_device_token(user, token):
    """Remove device token."""
    from apps.notifications.models import DeviceToken

    DeviceToken.objects.filter(user=user, device_token=token).update(is_active=False)


def _build_frontend_or_api_link(request, frontend_path: str, api_path: str) -> str:
    """Build frontend URL when configured; otherwise fall back to API URL or mobile deep link."""
    frontend_base = str(
        getattr(settings, "FRONTEND_BASE_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or ""
    ).rstrip("/")
    if frontend_base:
        return f"{frontend_base}/{frontend_path.lstrip('/')}"
    
    # Try mobile deep link as fallback
    from apps.accounts.views import _build_mobile_deeplink
    mobile_link = _build_mobile_deeplink(
        frontend_path.lstrip('/'),
        {},
    )
    if mobile_link:
        return mobile_link
    
    return request.build_absolute_uri(f"/{api_path.lstrip('/')}")


def _send_mobile_registration_email(request, user) -> None:
    """Send welcome and verification email for mobile registration."""
    verify_url = ""
    site_name = getattr(settings, "SITE_NAME", "CampusHub")
    try:
        token = generate_signed_verification_token(user)
        verify_url = _build_frontend_or_api_link(
            request,
            frontend_path=f"/verify-email/{token}",
            api_path=f"/api/auth/verify-email/{token}/",
        )
        sent = UserEmailService.send_welcome_email(
            user,
            verification_url=verify_url,
            raise_on_error=True,
        )
        if sent:
            return
    except Exception:
        logger.exception(
            "Failed to send mobile registration template email to %s",
            getattr(user, "email", ""),
        )

    try:
        EmailService.send_email(
            subject=f"Welcome to {site_name}! Please verify your email",
            message=(
                "Welcome to CampusHub.\n\n"
                + (
                    f"Verify your email using this link:\n{verify_url}"
                    if verify_url
                    else "Please verify your email from the verification message sent to you."
                )
            ),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send mobile registration fallback email to %s",
            getattr(user, "email", ""),
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_subscribe_topic(request):
    """
    Subscribe user device to a notification topic.
    Topics: 'announcements', 'resources', 'updates', 'all'
    """
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    topic = request.data.get("topic")
    device_token = request.data.get("device_token")

    if not topic or not device_token:
        return MobileResponse.error(
            message="topic and device_token required", request=request
        )

    valid_topics = ["announcements", "resources", "updates", "all"]
    if topic not in valid_topics:
        return MobileResponse.error(
            message=f"Invalid topic. Valid: {valid_topics}", request=request
        )

    result = fcm_service.subscribe_to_topic([device_token], topic)

    if result.get("success"):
        response = MobileResponse.success(
            message=f"Subscribed to {topic}", request=request
        )
        return cache_idempotent_response(request, response)
    return MobileResponse.error(
        message=result.get("error", "Subscription failed"), request=request
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_unsubscribe_topic(request):
    """Unsubscribe user device from a notification topic."""
    replay = get_cached_idempotent_response(request)
    if replay is not None:
        return replay

    topic = request.data.get("topic")
    device_token = request.data.get("device_token")

    if not topic or not device_token:
        return MobileResponse.error(
            message="topic and device_token required", request=request
        )

    result = fcm_service.unsubscribe_from_topic([device_token], topic)

    if result.get("success"):
        response = MobileResponse.success(
            message=f"Unsubscribed from {topic}", request=request
        )
        return cache_idempotent_response(request, response)
    return MobileResponse.error(
        message=result.get("error", "Unsubscription failed"), request=request
    )


# Import for resource requests
from apps.resources.models import ResourceRequest
from apps.resources.serializers import ResourceRequestSerializer, ResourceRequestCreateSerializer

# Import for gamification
from apps.gamification.models import Leaderboard


# Import for comments
from apps.comments.models import Comment
from apps.comments.serializers import CommentSerializer, CommentCreateSerializer


def _serialize_mobile_comment(comment, request):
    user = comment.user
    avatar = None
    if getattr(user, "profile_image", None):
        try:
            avatar = request.build_absolute_uri(user.profile_image.url)
        except Exception:
            avatar = None
    return {
        "id": str(comment.id),
        "text": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "rating": 0,
        "user": {
            "id": str(user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar": avatar,
        },
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_resource_comments(request, resource_id):
    """
    GET: List comments for a resource
    POST: Add a comment to a resource
    """
    if request.method == "GET":
        comments = Comment.objects.filter(
            resource_id=resource_id,
            parent__isnull=True  # Only top-level comments
        ).select_related('user').order_by('-created_at')

        data = [_serialize_mobile_comment(comment, request) for comment in comments]
        return MobileResponse.success(data=data, request=request)
    
    elif request.method == "POST":
        payload = request.data.copy()
        if "content" not in payload and "text" in payload:
            payload["content"] = payload.get("text")

        serializer = CommentCreateSerializer(
            data=payload,
            context={"resource_id": resource_id},
        )
        if serializer.is_valid():
            comment = Comment.objects.create(
                user=request.user,
                resource_id=resource_id,
                parent=serializer.validated_data.get("parent"),
                content=serializer.validated_data.get("content"),
            )
            return MobileResponse.success(
                data=_serialize_mobile_comment(comment, request),
                message="Comment added successfully",
                request=request,
            )
        return MobileResponse.error(message=serializer.errors, request=request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_leaderboard(request):
    """
    Get leaderboard rankings for mobile.
    Query params: period (daily, weekly, monthly, all_time)
    """
    period = request.query_params.get('period', 'all_time')
    
    # Normalize period
    valid_periods = ['daily', 'weekly', 'monthly', 'all_time']
    if period not in valid_periods:
        period = 'all_time'

    # Use the current gamification leaderboard service. The old mobile leaderboard model
    # shape (user/rank/points columns) diverged from the snapshot-based Leaderboard model.
    from apps.gamification.services import LeaderboardService

    leaderboard = LeaderboardService.get_leaderboard(
        leaderboard_type="global",
        period=period,
        limit=50,
    )

    rank_entry = LeaderboardService.get_user_rank(
        user=request.user,
        leaderboard_type="global",
        period=period,
    )
    user_rank = rank_entry.get("rank") if isinstance(rank_entry, dict) else None

    def split_name(value):
        cleaned = str(value or "").strip()
        if not cleaned:
            return ("", "")
        parts = cleaned.split()
        if len(parts) == 1:
            return (parts[0], "")
        return (parts[0], " ".join(parts[1:]))

    entries_data = []
    for entry in leaderboard or []:
        first_name, last_name = split_name(entry.get("user_name"))
        avatar = None
        profile_image = entry.get("profile_image")
        if profile_image:
            try:
                avatar = request.build_absolute_uri(profile_image)
            except Exception:
                avatar = profile_image

        entries_data.append(
            {
                "rank": int(entry.get("rank") or 0),
                "user": {
                    "id": str(entry.get("user_id") or ""),
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": str(entry.get("user_email") or ""),
                    "profile_image_url": avatar,
                    "avatar": avatar,
                },
                "total_points": int(entry.get("points") or 0),
                "total_uploads": 0,
                "total_downloads": 0,
                "total_shares": 0,
            }
        )
    
    return MobileResponse.success(
        data={
            "period": period,
            "user_rank": user_rank,
            "entries": entries_data,
        },
        request=request
    )


@api_view(["GET"])
@permission_classes([AllowAny])  # Allow unauthenticated access for mobile health checks
@throttle_classes([MobileUserRateThrottle])
def mobile_system_health(request):
    """
    Get system health metrics for admin users.
    Unauthenticated users get basic status, admin users get full health data.
    """
    # Check if user is authenticated and is admin
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    if not isinstance(request.user, User) or request.user.is_anonymous:
        # Unauthenticated - return basic status
        return MobileResponse.success(
            data={
                "status": "ok",
                "message": "Server is running"
            },
            request=request
        )
    
    # Only allow admin users for full health data
    if not request.user.is_staff and not request.user.is_superuser:
        return MobileResponse.error(
            message="Admin access required",
            request=request
        )
    
    from apps.admin_management.services import get_system_health
    from django.core.cache import cache
    
    health_data = get_system_health()
    
    # Add cache info
    try:
        cache.set("health_check", "ok", 10)
        cache_status = "healthy" if cache.get("health_check") == "ok" else "unhealthy"
        cache.delete("health_check")
    except Exception:
        cache_status = "unknown"
    
    # Add notification counts
    from apps.notifications.models import Notification
    try:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        total_count = Notification.objects.filter(
            recipient=request.user
        ).count()
    except Exception:
        unread_count = 0
        total_count = 0
    
    return MobileResponse.success(
        data={
            **health_data,
            "cache": {
                "status": cache_status
            },
            "notifications": {
                "unread_count": unread_count,
                "total_count": total_count
            }
        },
        request=request
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_resource_requests(request):
    """
    GET: List resource requests
    POST: Create a new resource request
    """
    if request.method == "GET":
        status_filter = request.query_params.get('status')
        queryset = ResourceRequest.objects.all()
        
        # Non-admin users can see their own requests plus community requests in scope
        if not request.user.is_staff and not request.user.is_superuser:
            scope_filter = Q()
            if getattr(request.user, "course_id", None):
                scope_filter |= Q(course_id=request.user.course_id)
            if getattr(request.user, "department_id", None):
                scope_filter |= Q(department_id=request.user.department_id)
            if getattr(request.user, "faculty_id", None):
                scope_filter |= Q(faculty_id=request.user.faculty_id)

            community_filter = Q(status="pending")
            if scope_filter:
                community_filter &= scope_filter

            queryset = queryset.filter(Q(requested_by=request.user) | community_filter)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        queryset = queryset.order_by('-priority', '-created_at')
        serializer = ResourceRequestSerializer(queryset, many=True, context={'request': request})
        return MobileResponse.success(data=serializer.data, request=request)
    
    elif request.method == "POST":
        serializer = ResourceRequestCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Get academic context from user
            # Faculty is on User model, not Profile
            
            resource_request = ResourceRequest.objects.create(
                title=serializer.validated_data.get('title'),
                description=serializer.validated_data.get('description'),
                requested_by=request.user,
                course=serializer.validated_data.get('course'),
                faculty=serializer.validated_data.get('faculty') or (request.user.faculty if hasattr(request.user, 'faculty') else None),
                department=serializer.validated_data.get('department'),
                priority=serializer.validated_data.get('priority', 'medium'),
            )
            
            # Notify admins and relevant students about new resource request
            try:
                from apps.accounts.models import User
                admins = User.objects.filter(is_staff=True, is_active=True).exclude(
                    id=request.user.id
                )

                student_scope = User.objects.filter(is_active=True, role="STUDENT").exclude(
                    id=request.user.id
                )
                if resource_request.course_id:
                    student_scope = student_scope.filter(course_id=resource_request.course_id)
                elif resource_request.department_id:
                    student_scope = student_scope.filter(department_id=resource_request.department_id)
                elif resource_request.faculty_id:
                    student_scope = student_scope.filter(faculty_id=resource_request.faculty_id)

                recipients = list(admins) + list(student_scope[:200])

                Notification.objects.bulk_create(
                    [
                        Notification(
                            recipient=recipient,
                            title="New Resource Request",
                            message=f"{request.user.full_name or request.user.email} requested: {resource_request.title}",
                            notification_type="resource_request",
                            link="/(student)/resource-requests",
                        )
                        for recipient in recipients
                    ]
                )

                # Try to send push notifications
                for recipient in recipients:
                    try:
                        fcm_service.send_notification(
                            user_id=recipient.id,
                            title="New Resource Request",
                            body=f"{request.user.full_name or request.user.email} requested: {resource_request.title}",
                        )
                    except Exception:
                        pass  # Skip push notification if it fails
            except Exception:
                pass  # Skip notification if it fails
            
            return MobileResponse.success(
                data={
                    'id': str(resource_request.id),
                    'title': resource_request.title,
                    'status': resource_request.status,
                },
                message='Resource request created successfully',
                request=request
            )
        return MobileResponse.error(message=serializer.errors, request=request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_upvote_resource_request(request, request_id):
    """Upvote a resource request."""
    try:
        resource_request = ResourceRequest.objects.get(id=request_id)
    except ResourceRequest.DoesNotExist:
        return MobileResponse.error(message='Request not found', request=request)
    
    # Check if user already upvoted
    if request.user in resource_request.requested_by_upvoted.all():
        resource_request.cancel_upvote(request.user)
        return MobileResponse.success(
            data={'upvotes': resource_request.upvotes, 'upvoted': False},
            message='Upvote removed',
            request=request
        )
    else:
        resource_request.upvote(request.user)
        return MobileResponse.success(
            data={'upvotes': resource_request.upvotes, 'upvoted': True},
            message='Upvoted successfully',
            request=request
        )


@permission_classes([AllowAny])
def mobile_animation(request):
    """
    Serve Lottie animation files for mobile app.
    
    Available animations:
    - loading: Spinner animation for loading states
    - success: Checkmark animation for success states
    - error: X mark animation for error states
    - empty: Folder with question mark for empty states
    """
    animation_name = request.GET.get('name', 'loading')
    
    # Map animation names to files
    animation_map = {
        'loading': 'loading.json',
        'success': 'success.json',
        'error': 'error.json',
        'empty': 'empty.json',
    }
    
    if animation_name not in animation_map:
        return MobileResponse.error(
            message=f'Animation "{animation_name}" not found. Available: {list(animation_map.keys())}',
            request=request
        )
    
    from django.http import FileResponse, Http404
    import os
    
    # Build the path to the animation file
    animation_dir = os.path.join(settings.BASE_DIR, 'static', 'animations')
    animation_path = os.path.join(animation_dir, animation_map[animation_name])
    
    if not os.path.exists(animation_path):
        return MobileResponse.error(
            message=f'Animation file not found',
            request=request
        )
    
    # Return the JSON file
    return FileResponse(
        open(animation_path, 'rb'),
        content_type='application/json'
    )


@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_widget_data(request):
    """
    Get widget data for home screen widgets.
    
    Supports widget types:
    - recent_files: Recently accessed/downloaded files
    - upcoming_events: Calendar events in the next 7 days
    - quick_actions: Quick action buttons for the user
    """
    widget_type = request.GET.get('widget_type', 'all')
    limit = min(int(request.GET.get('limit', 5)), 20)
    
    widgets_data = {}
    
    if widget_type in ['all', 'recent_files']:
        # Get recently accessed files from downloads
        try:
            from apps.downloads.models import Download
            recent_downloads = Download.objects.filter(
                user=request.user
            ).select_related('resource').order_by('-created_at')[:limit]
            
            widgets_data['recent_files'] = [
                {
                    'id': str(d.resource.id),
                    'title': d.resource.title,
                    'type': d.resource.get_resource_type_display(),
                    'thumbnail': getattr(d.resource.thumbnail, 'url', ''),
                    'downloaded_at': d.created_at.isoformat() if d.created_at else None,
                    'link': f'/resources/{d.resource.slug}/'
                }
                for d in recent_downloads if d.resource
            ]
        except Exception as e:
            logger.warning(f"Error getting recent files: {e}")
            widgets_data['recent_files'] = []
    
    if widget_type in ['all', 'upcoming_events']:
        # Get upcoming calendar events
        try:
            from apps.calendar.models import CalendarEvent
            from django.utils import timezone
            now = timezone.now()
            upcoming_events = CalendarEvent.objects.filter(
                Q(user=request.user) | Q(is_global=True),
                start_date__gte=now,
                start_date__lte=now + timezone.timedelta(days=7)
            ).order_by('start_date')[:limit]
            
            widgets_data['upcoming_events'] = [
                {
                    'id': str(e.id),
                    'title': e.title,
                    'description': e.description or '',
                    'start_date': e.start_date.isoformat() if e.start_date else None,
                    'end_date': e.end_date.isoformat() if e.end_date else None,
                    'location': e.location or '',
                    'event_type': e.event_type,
                    'link': f'/calendar/events/{e.id}/'
                }
                for e in upcoming_events
            ]
        except Exception as e:
            logger.warning(f"Error getting upcoming events: {e}")
            widgets_data['upcoming_events'] = []
    
    if widget_type in ['all', 'quick_actions']:
        # Get quick actions based on user context
        widgets_data['quick_actions'] = [
            {
                'id': 'upload',
                'title': 'Upload Resource',
                'icon': 'upload',
                'action': 'navigate',
                'link': '/resources/upload/',
                'color': '#4F46E5'
            },
            {
                'id': 'search',
                'title': 'Search',
                'icon': 'search',
                'action': 'navigate',
                'link': '/search/',
                'color': '#10B981'
            },
            {
                'id': 'bookmarks',
                'title': 'Bookmarks',
                'icon': 'bookmark',
                'action': 'navigate',
                'link': '/bookmarks/',
                'color': '#F59E0B'
            },
            {
                'id': 'library',
                'title': 'My Library',
                'icon': 'folder',
                'action': 'navigate',
                'link': '/library/',
                'color': '#8B5CF6'
            },
            {
                'id': 'notifications',
                'title': 'Notifications',
                'icon': 'bell',
                'action': 'navigate',
                'link': '/notifications/',
                'color': '#EF4444'
            }
        ]
    
    return MobileResponse.success(
        data=widgets_data,
        message='Widget data retrieved successfully',
        request=request
    )


@authentication_classes([JWTAuthentication])
@throttle_classes([MobileUserRateThrottle])
def mobile_widget_refresh(request):
    """
    Refresh widget data.
    
    Forces refresh of cached widget data and returns fresh data.
    """
    widget_type = request.GET.get('widget_type', 'all')
    
    # Clear cache for this user's widget data
    cache_key = f'mobile_widget_{request.user.id}_{widget_type}'
    cache.delete(cache_key)
    
    # Get fresh data
    return mobile_widget_data(request)


# =============================================================================
# Gesture API Views
# =============================================================================

@throttle_classes([MobileUserRateThrottle])
def mobile_gesture_settings(request):
    """
    Get or update gesture settings for the current user.
    
    GET: Returns current user's gesture configuration
    PUT: Updates gesture configuration
    """
    from apps.api.mobile_gestures import (
        GestureConfiguration,
        create_default_swipe_actions,
    )
    from .mobile_serializers import GestureConfigurationSerializer
    
    # Ensure default swipe actions exist
    create_default_swipe_actions()
    
    if request.method == "GET":
        config, created = GestureConfiguration.objects.get_or_create(
            user=request.user
        )
        serializer = GestureConfigurationSerializer(config)
        return MobileResponse.success(
            data=serializer.data,
            message="Gesture settings retrieved successfully"
        )
    
    elif request.method == "PUT":
        config, created = GestureConfiguration.objects.get_or_create(
            user=request.user
        )
        serializer = GestureConfigurationSerializer(config, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return MobileResponse.success(
                data=serializer.data,
                message="Gesture settings updated successfully"
            )
        
        return MobileResponse.error(
            error="validation_error",
            message="Invalid data",
            details=serializer.errors
        )


@throttle_classes([MobileUserRateThrottle])
def mobile_swipe_actions(request):
    """
    Get available swipe actions.
    
    GET: Returns list of all available swipe actions
    """
    from apps.api.mobile_gestures import SwipeAction
    from .mobile_serializers import SwipeActionSerializer
    
    if request.method == "GET":
        actions = SwipeAction.objects.filter(is_active=True).order_by("priority")
        serializer = SwipeActionSerializer(actions, many=True)
        return MobileResponse.success(
            data=serializer.data,
            message="Swipe actions retrieved successfully"
        )


@throttle_classes([MobileUserRateThrottle])
def mobile_user_swipe_mappings(request):
    """
    Get or update user swipe gesture mappings.
    
    GET: Returns user's gesture to action mappings
    PUT: Updates mappings
    """
    from apps.api.mobile_gestures import UserSwipeMapping, SwipeAction
    from .mobile_serializers import UserSwipeMappingSerializer
    
    if request.method == "GET":
        mappings = UserSwipeMapping.objects.filter(
            user=request.user
        ).select_related("action")
        
        # Add action_id to the serialized data
        data = []
        for mapping in mappings:
            item = {
                "id": str(mapping.id),
                "gesture_type": mapping.gesture_type,
                "direction": mapping.direction,
                "action_id": str(mapping.action.id) if mapping.action else None,
                "is_enabled": mapping.is_enabled,
                "screen": mapping.screen,
                "min_swipe_distance": mapping.min_swipe_distance,
                "max_swipe_time": mapping.max_swipe_time,
            }
            data.append(item)
        
        return MobileResponse.success(
            data=data,
            message="Swipe mappings retrieved successfully"
        )
    
    elif request.method == "PUT":
        mappings_data = request.data if isinstance(request.data, list) else [request.data]
        
        created_mappings = []
        errors = []
        
        for item in mappings_data:
            try:
                action_id = item.pop("action_id", None)
                
                if action_id:
                    action = SwipeAction.objects.get(id=action_id)
                    item["action"] = action
                
                mapping, created = UserSwipeMapping.objects.update_or_create(
                    user=request.user,
                    gesture_type=item.get("gesture_type"),
                    direction=item.get("direction", "any"),
                    screen=item.get("screen", ""),
                    defaults=item
                )
                created_mappings.append(str(mapping.id))
            except Exception as e:
                errors.append(str(e))
        
        if errors:
            return MobileResponse.error(
                error="mapping_error",
                message="Some mappings could not be saved",
                details={"errors": errors}
            )
        
        return MobileResponse.success(
            data={"mappings": created_mappings},
            message="Swipe mappings updated successfully"
        )


@throttle_classes([MobileUserRateThrottle])
def mobile_custom_gestures(request):
    """
    Manage custom gestures.
    
    GET: Returns user's custom gestures
    POST: Creates a new custom gesture
    PUT: Updates a custom gesture
    DELETE: Deletes a custom gesture
    """
    from apps.api.mobile_gestures import CustomGesture, SwipeAction, GestureConfiguration
    from .mobile_serializers import CustomGestureSerializer
    
    if request.method == "GET":
        gestures = CustomGesture.objects.filter(
            user=request.user,
            is_active=True
        ).order_by("-usage_count", "-created_at")
        
        data = []
        for gesture in gestures:
            item = {
                "id": str(gesture.id),
                "name": gesture.name,
                "description": gesture.description,
                "gesture_pattern": gesture.gesture_pattern,
                "min_match_score": gesture.min_match_score,
                "action_id": str(gesture.action.id) if gesture.action else None,
                "custom_action_name": gesture.custom_action_name,
                "custom_action_params": gesture.custom_action_params,
                "is_active": gesture.is_active,
                "usage_count": gesture.usage_count,
                "last_used": gesture.last_used,
                "created_at": gesture.created_at,
            }
            data.append(item)
        
        return MobileResponse.success(
            data=data,
            message="Custom gestures retrieved successfully"
        )
    
    elif request.method == "POST":
        # Check max custom gestures limit
        config, _ = GestureConfiguration.objects.get_or_create(user=request.user)
        current_count = CustomGesture.objects.filter(user=request.user, is_active=True).count()
        
        if current_count >= config.max_custom_gestures:
            return MobileResponse.error(
                error="limit_exceeded",
                message=f"Maximum number of custom gestures ({config.max_custom_gestures}) reached"
            )
        
        data = request.data
        action_id = data.pop("action_id", None)
        
        try:
            if action_id:
                action = SwipeAction.objects.get(id=action_id)
                data["action"] = action
            
            gesture = CustomGesture.objects.create(
                user=request.user,
                **data
            )
            
            return MobileResponse.success(
                data={"id": str(gesture.id)},
                message="Custom gesture created successfully",
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return MobileResponse.error(
                error="creation_error",
                message=str(e)
            )
    
    elif request.method == "DELETE":
        gesture_id = request.GET.get("id") or request.data.get("id")
        
        if not gesture_id:
            return MobileResponse.error(
                error="missing_id",
                message="Gesture ID is required"
            )
        
        try:
            gesture = CustomGesture.objects.get(id=gesture_id, user=request.user)
            gesture.is_active = False
            gesture.save()
            
            return MobileResponse.success(
                message="Custom gesture deleted successfully"
            )
        except CustomGesture.DoesNotExist:
            return MobileResponse.error(
                error="not_found",
                message="Custom gesture not found"
            )


@throttle_classes([MobileUserRateThrottle])
def mobile_gesture_analytics(request):
    """
    Record gesture analytics.
    
    POST: Records a gesture usage event
    GET: Returns user's gesture analytics summary
    """
    from apps.api.mobile_gestures import GestureAnalytics, SwipeAction
    from .mobile_serializers import GestureAnalyticsSerializer
    
    if request.method == "POST":
        data = request.data
        action_triggered_id = data.pop("action_triggered_id", None)
        
        try:
            if action_triggered_id:
                action = SwipeAction.objects.get(id=action_triggered_id)
                data["action_triggered"] = action
            
            analytics = GestureAnalytics.objects.create(
                user=request.user,
                **data
            )
            
            return MobileResponse.success(
                data={"id": str(analytics.id)},
                message="Gesture analytics recorded"
            )
        except Exception as e:
            return MobileResponse.error(
                error="recording_error",
                message=str(e)
            )
    
    elif request.method == "GET":
        # Get analytics summary
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        days = int(request.GET.get("days", 7))
        start_date = timezone.now() - timedelta(days=days)
        
        summary = GestureAnalytics.objects.filter(
            user=request.user,
            created_at__gte=start_date
        ).values("gesture_type").annotate(
            count=Count("id"),
            avg_duration=Avg("gesture_duration"),
            success_rate=Count("id", filter=models.Q(recognized=True))
        )
        
        return MobileResponse.success(
            data=list(summary),
            message="Analytics summary retrieved"
        )


# =============================================================================
# Haptic Feedback API Views
# =============================================================================

@throttle_classes([MobileUserRateThrottle])
def mobile_haptic_settings(request):
    """
    Get or update haptic feedback settings for the current user.
    
    GET: Returns current user's haptic feedback configuration
    PUT: Updates haptic feedback configuration
    """
    from apps.api.mobile_gestures import (
        HapticFeedbackConfiguration,
        create_default_haptic_patterns,
    )
    from .mobile_serializers import HapticFeedbackConfigurationSerializer
    
    # Ensure default haptic patterns exist
    create_default_haptic_patterns()
    
    if request.method == "GET":
        config, created = HapticFeedbackConfiguration.objects.get_or_create(
            user=request.user
        )
        serializer = HapticFeedbackConfigurationSerializer(config)
        return MobileResponse.success(
            data=serializer.data,
            message="Haptic settings retrieved successfully"
        )
    
    elif request.method == "PUT":
        config, created = HapticFeedbackConfiguration.objects.get_or_create(
            user=request.user
        )
        serializer = HapticFeedbackConfigurationSerializer(
            config, data=request.data, partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return MobileResponse.success(
                data=serializer.data,
                message="Haptic settings updated successfully"
            )
        
        return MobileResponse.error(
            error="validation_error",
            message="Invalid data",
            details=serializer.errors
        )


@throttle_classes([MobileUserRateThrottle])
def mobile_haptic_patterns(request):
    """
    Get available haptic patterns.
    
    GET: Returns list of all available haptic patterns
    """
    from apps.api.mobile_gestures import HapticPattern, create_default_haptic_patterns
    from .mobile_serializers import HapticPatternSerializer
    
    # Ensure default patterns exist
    create_default_haptic_patterns()
    
    if request.method == "GET":
        # Filter by category if provided
        category = request.GET.get("category")
        if category:
            patterns = HapticPattern.objects.filter(
                is_active=True, category=category
            ).order_by("name")
        else:
            patterns = HapticPattern.objects.filter(
                is_active=True
            ).order_by("category", "name")
        
        serializer = HapticPatternSerializer(patterns, many=True)
        
        # Get unique categories
        categories = list(
            HapticPattern.objects.filter(is_active=True)
            .values_list("category", flat=True)
            .distinct()
        )
        
        return MobileResponse.success(
            data={
                "patterns": serializer.data,
                "categories": categories
            },
            message="Haptic patterns retrieved successfully"
        )


@throttle_classes([MobileUserRateThrottle])
def mobile_custom_haptic_patterns(request):
    """
    Get, create, update, or delete custom haptic patterns.
    
    GET: Returns user's custom haptic patterns
    POST: Creates a new custom haptic pattern
    PUT: Updates an existing custom haptic pattern
    DELETE: Deletes a custom haptic pattern
    """
    from apps.api.mobile_gestures import CustomHapticPattern
    from .mobile_serializers import CustomHapticPatternSerializer
    
    if request.method == "GET":
        patterns = CustomHapticPattern.objects.filter(
            user=request.user
        ).order_by("-usage_count", "-created_at")
        serializer = CustomHapticPatternSerializer(patterns, many=True)
        return MobileResponse.success(
            data=serializer.data,
            message="Custom haptic patterns retrieved successfully"
        )
    
    elif request.method == "POST":
        serializer = CustomHapticPatternSerializer(data=request.data)
        
        if serializer.is_valid():
            pattern = CustomHapticPattern.objects.create(
                user=request.user,
                **serializer.validated_data
            )
            return MobileResponse.success(
                data=CustomHapticPatternSerializer(pattern).data,
                message="Custom haptic pattern created successfully",
                status=status.HTTP_201_CREATED
            )
        
        return MobileResponse.error(
            error="validation_error",
            message="Invalid data",
            details=serializer.errors
        )
    
    elif request.method == "PUT":
        pattern_id = request.data.get("id")
        if not pattern_id:
            return MobileResponse.error(
                error="missing_id",
                message="Pattern ID is required"
            )
        
        try:
            pattern = CustomHapticPattern.objects.get(
                id=pattern_id, user=request.user
            )
        except CustomHapticPattern.DoesNotExist:
            return MobileResponse.error(
                error="not_found",
                message="Custom pattern not found"
            )
        
        serializer = CustomHapticPatternSerializer(
            pattern, data=request.data, partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return MobileResponse.success(
                data=serializer.data,
                message="Custom haptic pattern updated successfully"
            )
        
        return MobileResponse.error(
            error="validation_error",
            message="Invalid data",
            details=serializer.errors
        )
    
    elif request.method == "DELETE":
        pattern_id = request.GET.get("id")
        if not pattern_id:
            return MobileResponse.error(
                error="missing_id",
                message="Pattern ID is required"
            )
        
        try:
            pattern = CustomHapticPattern.objects.get(
                id=pattern_id, user=request.user
            )
            pattern.delete()
            return MobileResponse.success(
                message="Custom haptic pattern deleted successfully"
            )
        except CustomHapticPattern.DoesNotExist:
            return MobileResponse.error(
                error="not_found",
                message="Custom pattern not found"
            )


@throttle_classes([MobileUserRateThrottle])
def mobile_haptic_mappings(request):
    """
    Get or update haptic action mappings.
    
    GET: Returns user's haptic action mappings
    PUT: Updates haptic action mappings
    """
    from apps.api.mobile_gestures import HapticActionMapping, HapticPattern, CustomHapticPattern
    from .mobile_serializers import HapticActionMappingSerializer
    
    if request.method == "GET":
        mappings = HapticActionMapping.objects.filter(
            user=request.user
        ).select_related("pattern", "custom_pattern")
        
        # Add pattern info to serialized data
        data = []
        for mapping in mappings:
            item = {
                "id": str(mapping.id),
                "action": mapping.action,
                "pattern_id": str(mapping.pattern.id) if mapping.pattern else None,
                "custom_pattern_id": str(mapping.custom_pattern.id) if mapping.custom_pattern else None,
                "intensity_override": mapping.intensity_override,
                "is_enabled": mapping.is_enabled,
            }
            data.append(item)
        
        return MobileResponse.success(
            data=data,
            message="Haptic mappings retrieved successfully"
        )
    
    elif request.method == "PUT":
        # Expecting a list of mappings
        mappings_data = request.data if isinstance(request.data, list) else [request.data]
        
        created_mappings = []
        for item in mappings_data:
            pattern_id = item.pop("pattern_id", None)
            custom_pattern_id = item.pop("custom_pattern_id", None)
            
            mapping, _ = HapticActionMapping.objects.update_or_create(
                user=request.user,
                action=item.get("action"),
                defaults=item
            )
            
            # Set pattern relationships
            if pattern_id:
                try:
                    mapping.pattern = HapticPattern.objects.get(id=pattern_id)
                except HapticPattern.DoesNotExist:
                    pass
            
            if custom_pattern_id:
                try:
                    mapping.custom_pattern = CustomHapticPattern.objects.get(
                        id=custom_pattern_id, user=request.user
                    )
                except CustomHapticPattern.DoesNotExist:
                    pass
            
            mapping.save()
            created_mappings.append(mapping)
        
        return MobileResponse.success(
            data={"updated_count": len(created_mappings)},
            message="Haptic mappings updated successfully"
        )
