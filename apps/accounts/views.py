"""
Views for accounts app.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.db import connection, models
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTTokenRefreshView

from apps.core.emails import EmailService

from .authentication import generate_tokens_for_user
from .models import Profile, User, UserActivity, UserPreference
from .permissions import IsAdminUser
from .serializers import (LoginSerializer, PasswordChangeSerializer,
                          PasswordResetConfirmSerializer,
                          PasswordResetRequestSerializer,
                          ProfileDetailSerializer,
                          ProfilePhotoUploadSerializer, ProfileSerializer,
                          UserActivitySerializer, UserDetailSerializer,
                          UserPreferenceSerializer, UserRegistrationSerializer,
                          UserSerializer, UserUpdateSerializer)
from .services import ProfileCompletionService, PasswordlessAuthService
from .signals import log_user_activity
from .verification import (EmailVerificationToken, PasswordResetToken,
                           generate_signed_password_reset_token,
                           generate_signed_verification_token,
                           validate_signed_password_reset_token,
                           validate_signed_verification_token)

logger = logging.getLogger(__name__)


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
    mobile_link = _build_mobile_deeplink(
        frontend_path.lstrip('/'),
        {},
    )
    if mobile_link:
        return mobile_link
    
    return request.build_absolute_uri(f"/{api_path.lstrip('/')}")


def _build_mobile_deeplink(path: str, query: dict | None = None) -> str:
    """Build deep-link URL for mobile app routes."""
    scheme = str(getattr(settings, "MOBILE_DEEPLINK_SCHEME", "") or "").strip()
    if not scheme:
        return ""
    base = f"{scheme}://{path.lstrip('/')}"
    if not query:
        return base
    encoded = urlencode({k: v for k, v in query.items() if v is not None})
    return f"{base}?{encoded}" if encoded else base


def _build_password_reset_link(request, token: str) -> str:
    """
    Build password reset link in priority order:
    1) Frontend URL (web) - if FRONTEND_URL is configured
    2) Mobile deep-link (campushub://reset-password?token=xxx) - for mobile app
    3) API absolute URL fallback - works as a web URL
    """
    frontend_base = str(
        getattr(settings, "FRONTEND_BASE_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or ""
    ).rstrip("/")
    if frontend_base:
        return f"{frontend_base}/password-reset/{token}"

    # Build mobile deep link with token as query parameter
    mobile_link = _build_mobile_deeplink(
        "reset-password",
        query={"token": token},
    )
    if mobile_link:
        return mobile_link

    # Fallback to API URL which can be opened in a browser
    return request.build_absolute_uri(f"/api/auth/password/reset/confirm/{token}/")


def _send_template_email_with_fallback(
    *,
    subject: str,
    template_name: str,
    context: dict,
    fallback_message: str,
    recipient_email: str,
) -> bool:
    """
    Send template email and fall back to plain text if template flow fails.
    """
    try:
        sent = EmailService.send_template_email(
            template_name=template_name,
            context=context,
            subject=subject,
            recipient_list=[recipient_email],
            raise_on_error=True,
        )
        return bool(sent)
    except Exception:
        logger.exception(
            "Template email send failed for template '%s' to %s",
            template_name,
            recipient_email,
        )
        try:
            return EmailService.send_email(
                subject=subject,
                message=fallback_message,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                "Fallback plain email send failed for subject '%s' to %s",
                subject,
                recipient_email,
            )
            return False


def _model_table_exists(model_class):
    """Check whether a model table exists in the current database."""
    return model_class._meta.db_table in connection.introspection.table_names()


def _extract_refresh_token(request) -> str:
    """Accept both legacy and mobile refresh token field names."""
    return str(
        request.data.get("refresh")
        or request.data.get("refresh_token")
        or ""
    ).strip()


def _parse_boolean_flag(value) -> bool:
    """Parse booleans from JSON booleans, ints, and common string values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _is_suspicious_login(user, request) -> bool:
    """
    Detect possible suspicious login by comparing current fingerprint
    against recent successful login activity.
    """
    from apps.core.utils import get_client_ip, get_user_agent

    current_ip = get_client_ip(request)
    current_agent = get_user_agent(request)
    if not current_ip and not current_agent:
        return False

    history = UserActivity.objects.filter(
        user=user,
        action="login",
    ).order_by(
        "-created_at"
    )[:20]

    if not history:
        return False

    known_ips = {item.ip_address for item in history if item.ip_address}
    known_agents = {item.user_agent for item in history if item.user_agent}
    if not known_ips and not known_agents:
        return False

    is_new_ip = bool(current_ip and current_ip not in known_ips)
    is_new_agent = bool(current_agent and current_agent not in known_agents)

    return is_new_ip and (is_new_agent or len(known_ips) >= 2)


def _send_suspicious_login_alert(user, request):
    """Send in-app and email alert for suspicious login attempts."""
    from apps.core.utils import get_client_ip, get_user_agent

    current_ip = get_client_ip(request) or "unknown"
    current_agent = (get_user_agent(request) or "unknown")[:180]
    occurred_at = timezone.now()

    try:
        from apps.notifications.services import NotificationService

        NotificationService.create_notification(
            recipient=user,
            title="Suspicious Login Detected",
            message=(
                f"We noticed a login from a new device or location "
                f"({current_ip}) on {occurred_at:%Y-%m-%d %H:%M %Z}."
            ),
            notification_type="system",
            link="/profile/security/",
        )
    except Exception:
        pass

    try:
        preferences = getattr(user, "preferences", None)
        if preferences and not preferences.email_notifications:
            return

        EmailService.send_email(
            subject="CampusHub security alert",
            message=(
                "We detected a sign in from a new device or location.\n\n"
                f"Time: {occurred_at:%Y-%m-%d %H:%M %Z}\n"
                f"IP: {current_ip}\n"
                f"Device: {current_agent}\n\n"
                "If this was not you, change your password immediately."
            ),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send suspicious login email to %s", user.email)


class RegisterView(generics.CreateAPIView):
    """API endpoint for user registration."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        payload = request.data.copy()
        # Backward-compatible aliases used by some legacy clients/tests.
        if payload.get("password1") and not payload.get("password"):
            payload["password"] = payload.get("password1")
        if payload.get("password2") and not payload.get("password_confirm"):
            payload["password_confirm"] = payload.get("password2")
        if payload.get("username") and not payload.get("full_name"):
            payload["full_name"] = payload.get("username")

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens
        tokens = generate_tokens_for_user(user)

        # Auto-send welcome + verification email.
        try:
            token = generate_signed_verification_token(user)
            verify_url = _build_frontend_or_api_link(
                request,
                frontend_path=f"/verify-email/{token}",
                api_path=f"/api/auth/verify-email/{token}/",
            )
            _send_template_email_with_fallback(
                subject=f"Welcome to {getattr(settings, 'SITE_NAME', 'CampusHub')}!",
                template_name="welcome",
                context={
                    "user": user,
                    "verification_url": verify_url,
                    "site_name": getattr(settings, "SITE_NAME", "CampusHub"),
                },
                fallback_message=(
                    "Welcome to CampusHub.\n\n"
                    f"Verify your email using this link:\n{verify_url}"
                ),
                recipient_email=user.email,
            )
        except Exception:
            logger.exception("Failed to queue registration email for %s", user.email)

        # Log activity
        log_user_activity(user, "login", "User registered", request)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "tokens": tokens,
                "message": "Registration successful.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    API endpoint for user login.

    POST /api/auth/login/
    {
        "email": "user@example.com",
        "password": "password",
        "remember_me": true  # Optional - extends session to 30 days
    }
    """

    permission_classes = [AllowAny]

    def post(self, request, **kwargs):
        # Support both email and registration_number
        email = (request.data.get("email") or "").strip().lower()
        registration_number = (request.data.get("registration_number") or "").strip()
        
        # Use email for rate limiting if provided
        login_identifier = email or registration_number
        attempts_key = f"auth:failed-login:{login_identifier}"
        current_attempts = cache.get(attempts_key, 0) if login_identifier else 0
        
        if login_identifier and current_attempts >= 5:
            return Response(
                {"detail": "Too many failed login attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            if login_identifier:
                cache.set(attempts_key, current_attempts + 1, timeout=15 * 60)
            raise
        user = serializer.validated_data["user"]
        if login_identifier:
            cache.delete(attempts_key)

        # Check for remember_me flag
        remember_me = _parse_boolean_flag(request.data.get("remember_me", False))

        # Generate tokens (with remember_me, stays logged in longer)
        tokens = generate_tokens_for_user(user, remember_me=remember_me)

        # Track active session (JWT refresh token)
        try:
            from .services import register_user_session

            register_user_session(user, request, tokens.get("refresh"))
        except Exception:
            logger.exception("Failed to register user session for %s", user.email)

        # Update last login
        user.update_last_login()
        try:
            from apps.gamification.services import GamificationService

            GamificationService.record_login(user)
        except Exception:
            logger.exception("Failed to record login gamification for user_id=%s", user.id)

        if _is_suspicious_login(user, request):
            _send_suspicious_login_alert(user, request)

        # Log activity
        log_user_activity(user, "login", "User logged in", request)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "tokens": tokens,
                "message": "Login successful.",
                "remember_me": remember_me,
            }
        )


class LogoutView(APIView):
    """API endpoint for user logout."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Blacklist the refresh token
            refresh_token = _extract_refresh_token(request)
            if refresh_token:
                token = OutstandingToken.objects.filter(token=refresh_token).first()
                if token:
                    BlacklistedToken.objects.get_or_create(token=token)

            try:
                from .services import deactivate_user_session

                deactivate_user_session(request.user, refresh_token)
            except Exception:
                logger.exception("Failed to deactivate session for %s", request.user.email)

            # Log activity
            log_user_activity(request.user, "logout", "User logged out", request)

            return Response(
                {"message": "Logout successful."}, status=status.HTTP_200_OK
            )
        except Exception:
            logger.exception("Logout token blacklisting failed for user_id=%s", request.user.id)
            return Response(
                {"message": "Logout successful."}, status=status.HTTP_200_OK
            )


class DeleteAccountView(APIView):
    """Schedule account deletion with a 7-day recovery window."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        password = str(request.data.get("password") or "")

        if not password or not user.check_password(password):
            return Response({"detail": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_deleted:
            return Response(
                {
                    "message": "Account deletion already scheduled.",
                    "scheduled_for": user.deletion_scheduled_at,
                },
                status=status.HTTP_200_OK,
            )

        now = timezone.now()
        user.is_active = False
        user.is_deleted = True
        user.deleted_at = now
        user.deletion_scheduled_at = now + timezone.timedelta(days=7)
        user.save(
            update_fields=[
                "is_active",
                "is_deleted",
                "deleted_at",
                "deletion_scheduled_at",
                "updated_at",
            ]
        )

        log_user_activity(user, "user_deactivated", "User requested account deletion", request)

        return Response(
            {
                "message": "Account deletion scheduled.",
                "scheduled_for": user.deletion_scheduled_at,
            },
            status=status.HTTP_200_OK,
        )


class JWTTokenRefreshView(SimpleJWTTokenRefreshView):
    """API endpoint for token refresh."""

    permission_classes = [AllowAny]


class UserSessionsView(APIView):
    """List active sessions for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import UserSession

        sessions = UserSession.objects.filter(
            user=request.user, is_active=True, expires_at__gt=timezone.now()
        ).order_by("-last_activity")

        data = [
            {
                "session_key": session.session_key,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "expires_at": session.expires_at,
            }
            for session in sessions
        ]

        return Response({"results": data, "count": len(data)})


class UserSessionRevokeView(APIView):
    """Revoke one or more sessions for the current user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import UserSession

        session_key = str(request.data.get("session_key") or "").strip()
        revoke_all = bool(request.data.get("revoke_all", False))

        if not session_key and not revoke_all:
            return Response({"detail": "session_key or revoke_all is required."}, status=400)

        sessions = UserSession.objects.filter(user=request.user, is_active=True)
        if session_key:
            sessions = sessions.filter(session_key=session_key)

        revoked = 0
        for session in sessions:
            try:
                outstanding = OutstandingToken.objects.filter(
                    user=request.user, jti=session.session_key
                ).first()
                if outstanding:
                    BlacklistedToken.objects.get_or_create(token=outstanding)
            except Exception:
                logger.exception("Failed to blacklist session token for user_id=%s", request.user.id)
            session.is_active = False
            session.save(update_fields=["is_active", "last_activity"])
            revoked += 1

        return Response({"message": "Sessions revoked", "revoked": revoked})


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint to get and update user profile.

    GET /api/profile/
    PATCH /api/profile/
    """

    serializer_class = ProfileDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()

        # Separate user and profile data
        user_fields = [
            "full_name",
            "phone_number",
            "registration_number",
            "faculty",
            "department",
            "course",
            "year_of_study",
            "semester",
            "profile_image",
        ]
        profile_fields = [
            "bio",
            "date_of_birth",
            "address",
            "city",
            "country",
            "website",
            "facebook",
            "twitter",
            "linkedin",
        ]

        # Update user fields
        user_data = {}
        for field in user_fields:
            if field in request.data:
                user_data[field] = request.data[field]

        if user_data:
            user_serializer = UserUpdateSerializer(
                user, data=user_data, partial=True, context={"request": request}
            )
            user_serializer.is_valid(raise_exception=True)
            user_serializer.save()

        # Update profile fields
        profile_data = {}
        for field in profile_fields:
            if field in request.data:
                profile_data[field] = request.data[field]

        if profile_data:
            profile_obj, _ = Profile.objects.get_or_create(user=user)
            profile_serializer = ProfileSerializer(
                profile_obj, data=profile_data, partial=True
            )
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()

        return Response(
            ProfileDetailSerializer(user, context={"request": request}).data
        )


class PasswordChangeView(APIView):
    """
    API endpoint for changing password.

    POST /api/profile/change-password/

    Note: Users who signed up with Google or Microsoft cannot change their password.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if user can change password (not OAuth user)
        if request.user.auth_provider != "email":
            return Response(
                {
                    "error": f"Cannot change password for {request.user.auth_provider} accounts. "
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Password changed successfully."}, status=status.HTTP_200_OK
        )


class PasswordResetRequestView(APIView):
    """API endpoint for requesting password reset."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            token = generate_signed_password_reset_token(user)
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
                    "Password reset email delivery failed for user_id=%s email=%s",
                    user.id,
                    user.email,
                )

        return Response(
            {"message": "Password reset email sent."}, status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """API endpoint for confirming password reset."""

    permission_classes = [AllowAny]

    @extend_schema(operation_id="api_auth_password_reset_confirm_uid_token_create")
    def post(self, request, token, uidb64=None):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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
            return Response(
                {"detail": "Invalid or expired reset token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])

        return Response(
            {"message": "Password reset successful."}, status=status.HTTP_200_OK
        )


class PasswordResetConfirmTokenOnlyView(PasswordResetConfirmView):
    """Backward-compatible token-only reset confirm endpoint."""

    @extend_schema(operation_id="api_auth_password_reset_confirm_token_create")
    def post(self, request, token):
        return super().post(request, token=token, uidb64=None)


class EmailVerificationView(APIView):
    """Verify user email using stateless token."""

    permission_classes = [AllowAny]

    def get(self, request, token):
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
            return Response(
                {"detail": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified", "updated_at"])
            try:
                from apps.gamification.services import GamificationService

                GamificationService.record_email_verification(user)
            except Exception:
                logger.exception(
                    "Failed to record email verification gamification for user_id=%s",
                    user.id,
                )

        return Response(
            {"message": "Email verified successfully."}, status=status.HTTP_200_OK
        )


class ResendVerificationEmailView(APIView):
    """Resend email verification link."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email=email, is_active=True).first()
        if user and not user.is_verified:
            try:
                token = generate_signed_verification_token(user)
                verify_url = _build_frontend_or_api_link(
                    request,
                    frontend_path=f"/verify-email/{token}",
                    api_path=f"/api/auth/verify-email/{token}/",
                )
                _send_template_email_with_fallback(
                    subject=f"Verify your {getattr(settings, 'SITE_NAME', 'CampusHub')} account",
                    template_name="welcome",
                    context={
                        "user": user,
                        "verification_url": verify_url,
                        "site_name": getattr(settings, "SITE_NAME", "CampusHub"),
                    },
                    fallback_message=(
                        "Verify your email using this link:\n"
                        f"{verify_url}"
                    ),
                    recipient_email=user.email,
                )
            except Exception:
                logger.exception(
                    "Failed to resend verification email for %s", user.email
                )

        return Response(
            {"message": "If that account exists, a verification email has been sent."},
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users (admin only)."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return UserDetailSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = User.objects.all()

        # Filter by role
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)

        # Filter by is_active
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        # Filter by is_verified
        is_verified = self.request.query_params.get("is_verified")
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == "true")

        # Search by email or full_name
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(email__icontains=search)
                | models.Q(full_name__icontains=search)
                | models.Q(registration_number__icontains=search)
            )

        return queryset


class UserActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing user activity."""

    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserActivity.objects.none()
        return UserActivity.objects.filter(user=self.request.user)


# ============================================
# New Profile Management Views
# ============================================


class ProfilePhotoUploadView(APIView):
    """
    API endpoint for uploading profile photo.

    POST /api/profile/photo/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProfilePhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        try:
            user.profile_image = serializer.validated_data["profile_image"]
            user.save()
        except Exception as exc:
            logger.exception("Failed to upload profile photo for user %s", user.id)
            try:
                from cloudinary.exceptions import AuthorizationRequired

                if isinstance(exc, AuthorizationRequired):
                    return Response(
                        {
                            "message": "Cloud storage authorization failed. Please verify Cloudinary credentials.",
                            "detail": "CLOUDINARY_AUTH_REQUIRED",
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
            except Exception:
                # Cloudinary not installed or unexpected error, fall through to generic response.
                pass
            return Response(
                {"message": "Failed to upload profile photo."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Profile photo uploaded successfully.",
                "profile_image": (
                    request.build_absolute_uri(user.profile_image.url)
                    if user.profile_image
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class ProfilePhotoDeleteView(APIView):
    """
    API endpoint for deleting profile photo.

    DELETE /api/profile/photo/
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        if user.profile_image:
            user.profile_image.delete()
            user.profile_image = None
            user.save()

            return Response(
                {"message": "Profile photo deleted successfully."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "No profile photo to delete."}, status=status.HTTP_404_NOT_FOUND
        )


class UserSearchView(APIView):
    """
    API endpoint for searching users.

    GET /api/accounts/users/search/?q=query
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"detail": "Query must be at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Exclude current user from results
        users = User.objects.filter(
            models.Q(email__icontains=query)
            | models.Q(full_name__icontains=query)
            | models.Q(registration_number__icontains=query)
            | models.Q(username__icontains=query)
        ).exclude(id=request.user.id)[:20]

        # Serialize with limited fields
        from .serializers import UserSerializer
        serializer = UserSerializer(
            users, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ProfilePreferencesView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for getting and updating user preferences.

    GET /api/profile/preferences/
    PATCH /api/profile/preferences/
    """

    serializer_class = UserPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        preferences, _ = UserPreference.objects.get_or_create(user=self.request.user)
        return preferences


class ProfileCompletionView(APIView):
    """
    API endpoint for getting profile completion status.

    GET /api/profile/completion/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        completion = ProfileCompletionService.calculate_completion(request.user)
        return Response(completion, status=status.HTTP_200_OK)


class ProfileLinkedAccountsView(APIView):
    """
    API endpoint for viewing linked social accounts.

    GET /api/profile/linked-accounts/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import LinkedAccount
        from .serializers import LinkedAccountSerializer

        linked_accounts = LinkedAccount.objects.filter(
            user=request.user, is_active=True
        )

        # Include auth_provider as a linked account
        providers = (
            [request.user.auth_provider]
            if request.user.auth_provider != "email"
            else []
        )
        providers += list(linked_accounts.values_list("provider", flat=True))

        return Response(
            {
                "linked_providers": list(set(providers)),
                "accounts": LinkedAccountSerializer(linked_accounts, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class ProfileLinkedAccountUnlinkView(APIView):
    """API endpoint for unlinking a social account."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = str(request.data.get("provider") or "").strip().lower()
        if not provider:
            return Response({"detail": "provider is required."}, status=status.HTTP_400_BAD_REQUEST)

        from .services import LinkedAccountService

        success = LinkedAccountService.unlink_account(request.user, provider)
        if success:
            return Response({"message": f"{provider} account unlinked."})
        return Response({"detail": "Account not linked."}, status=status.HTTP_400_BAD_REQUEST)


class MagicLinkRequestView(APIView):
    """Send a short-lived magic login link to the user's email."""

    permission_classes = [AllowAny]

    @extend_schema(summary="Request magic link", description="Send a magic login link to email")
    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.core.utils import get_client_ip

        result = PasswordlessAuthService.request_magic_link(
            email=email,
            ip_address=get_client_ip(request),
        )
        if not result["success"]:
            response_status = (
                status.HTTP_429_TOO_MANY_REQUESTS
                if "too many" in result["message"].lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result["message"]}, status=response_status)

        return Response({"detail": result["message"]})


class MagicLinkConsumeView(APIView):
    """Exchange a magic link token for JWT access/refresh."""

    permission_classes = [AllowAny]

    @extend_schema(summary="Consume magic link", description="Exchange magic link token for JWTs")
    def post(self, request):
        token = str(request.data.get("token") or request.query_params.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required"}, status=status.HTTP_400_BAD_REQUEST)

        from apps.core.utils import get_client_ip, get_user_agent

        result = PasswordlessAuthService.consume_magic_link(
            token=token,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        if not result["success"]:
            return Response({"detail": result["message"]}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(id=result["user_id"], is_active=True)
        user.update_last_login()
        try:
            from .services import register_user_session

            register_user_session(user, request, result.get("refresh"))
        except Exception:
            logger.exception("Failed to register magic-link session for %s", user.email)

        log_user_activity(user, "login", "User logged in with magic link", request)
        return Response(
            {
                "access": result["access"],
                "refresh": result["refresh"],
                "token_type": "magic_link",
                "message": result["message"],
                "expires_in": settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
            },
            status=status.HTTP_200_OK,
        )


# ==================== Passkey (WebAuthn/FIDO2) Views ====================


class PasskeyRegistrationStartView(APIView):
    """
    Start passkey registration - get options for the authenticator.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = None

    @extend_schema(
        summary="Start passkey registration",
        description="Get options to register a new passkey for the user"
    )
    def post(self, request):
        passkey_name = request.data.get("name", f"Passkey {request.user.email.split('@')[0]}")

        result = PasswordlessAuthService.get_passkey_registration_options(
            request.user, passkey_name
        )

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result["options"], status=status.HTTP_200_OK)


class PasskeyRegistrationCompleteView(APIView):
    """
    Complete passkey registration - verify and store the credential.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = None

    @extend_schema(
        summary="Complete passkey registration",
        description="Verify and store the passkey credential"
    )
    def post(self, request):
        credential_data = request.data.get("credential")
        if not credential_data:
            return Response(
                {"detail": "credential is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        passkey_name = request.data.get("name")

        result = PasswordlessAuthService.verify_passkey_registration(
            request.user, credential_data, passkey_name
        )

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": "Passkey registered successfully",
                "passkey_id": result["passkey_id"],
            },
            status=status.HTTP_201_CREATED
        )


class PasskeyAuthenticationStartView(APIView):
    """
    Start passkey authentication - get options for the authenticator.
    """

    permission_classes = [AllowAny]
    serializer_class = None

    @extend_schema(
        summary="Start passkey authentication",
        description="Get options for authenticating with a passkey"
    )
    def post(self, request):
        # Optional user ID if logging in with a specific user's passkeys
        user_id = request.data.get("user_id")

        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id, is_active=True)
            except User.DoesNotExist:
                pass

        result = PasswordlessAuthService.get_passkey_authentication_options(user)

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result["options"], status=status.HTTP_200_OK)


class PasskeyAuthenticationCompleteView(APIView):
    """
    Complete passkey authentication - verify and return JWT tokens.
    """

    permission_classes = [AllowAny]
    serializer_class = None

    @extend_schema(
        summary="Complete passkey authentication",
        description="Verify passkey and return JWT tokens"
    )
    def post(self, request):
        credential_data = request.data.get("credential")
        if not credential_data:
            return Response(
                {"detail": "credential is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = PasswordlessAuthService.verify_passkey_authentication(credential_data)

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "access": result["access"],
                "refresh": result["refresh"],
                "token_type": "passkey",
                "user_id": result["user_id"],
                "expires_in": settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
            },
            status=status.HTTP_200_OK
        )


class UserPasskeysView(APIView):
    """
    List and manage user's passkeys.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = None

    @extend_schema(
        summary="List user passkeys",
        description="Get all passkeys for the current user"
    )
    def get(self, request):
        passkeys = PasswordlessAuthService.list_user_passkeys(request.user)
        return Response(passkeys, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete a passkey",
        description="Delete a specific passkey"
    )
    def delete(self, request):
        passkey_id = request.data.get("passkey_id")
        if not passkey_id:
            return Response(
                {"detail": "passkey_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = PasswordlessAuthService.delete_user_passkey(
            request.user, passkey_id
        )

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"message": result["message"]}, status=status.HTTP_200_OK)


class PasskeyUpdateView(APIView):
    """
    Update passkey details (e.g., name).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = None

    @extend_schema(
        summary="Update passkey",
        description="Update passkey name"
    )
    def patch(self, request):
        passkey_id = request.data.get("passkey_id")
        new_name = request.data.get("name")

        if not passkey_id or not new_name:
            return Response(
                {"detail": "passkey_id and name are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = PasswordlessAuthService.update_passkey_name(
            request.user, passkey_id, new_name
        )

        if not result["success"]:
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"message": result["message"]}, status=status.HTTP_200_OK)
