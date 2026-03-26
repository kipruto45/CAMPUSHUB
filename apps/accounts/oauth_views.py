"""
OAuth2 views for Google and Microsoft authentication.
"""

import logging
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.emails import EmailService, get_frontend_base_url

from .serializers import UserSerializer
from .social_auth import (SocialAuthService, get_google_provider_config,
                          get_microsoft_provider_config)

User = get_user_model()
logger = logging.getLogger(__name__)


class MobileHttpResponseRedirect(HttpResponseRedirect):
    """Allow secure mobile deep-link redirects."""

    allowed_schemes = ["http", "https", "ftp", "campushub", "exp"]


def _build_allowed_http_hosts(request=None) -> set[str]:
    allowed_hosts = {"localhost", "127.0.0.1", "10.0.2.2"}
    frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
    if frontend_url:
        parsed = urlparse(frontend_url)
        if parsed.hostname:
            allowed_hosts.add(parsed.hostname.lower())
    if request is not None:
        try:
            request_host = (request.get_host() or "").split(":")[0].strip().lower()
            if request_host:
                allowed_hosts.add(request_host)
        except Exception:
            pass
    return allowed_hosts


def _is_allowed_mobile_redirect_uri(redirect_uri: str, request=None) -> bool:
    parsed = urlparse(str(redirect_uri or "").strip())
    if not parsed.scheme:
        return False

    scheme = parsed.scheme.lower()
    if scheme in {"campushub", "exp"}:
        return True

    if scheme in {"http", "https"}:
        host = (parsed.hostname or "").lower()
        return host in _build_allowed_http_hosts(request=request)

    return False


def _resolve_redirect_uri(request, fallback: str) -> str:
    redirect_uri = ""
    if hasattr(request, "data"):
        redirect_uri = str(request.data.get("redirect_uri") or "").strip()
    if not redirect_uri:
        redirect_uri = str(request.query_params.get("redirect_uri") or "").strip()

    if redirect_uri and _is_allowed_mobile_redirect_uri(redirect_uri, request=request):
        return redirect_uri
    return fallback


def _build_mobile_callback_url(provider: str, params: dict) -> str:
    scheme = str(getattr(settings, "MOBILE_DEEPLINK_SCHEME", "campushub") or "campushub")
    base = f"{scheme}://callback/{provider}"
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return f"{base}?{query}" if query else base


def _build_frontend_or_api_link(request, frontend_path: str, api_path: str) -> str:
    """Build frontend URL when configured; otherwise fall back to API URL or mobile deep link."""
    frontend_base = str(
        getattr(settings, "FRONTEND_BASE_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or getattr(settings, "RESOURCE_SHARE_BASE_URL", "")
        or getattr(settings, "WEB_APP_URL", "")
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


def _build_auth_success_payload(user, tokens: dict, message: str) -> dict:
    """Keep OAuth login responses aligned with the rest of the auth API."""
    access = str(tokens.get("access") or "")
    refresh = str(tokens.get("refresh") or "")
    return {
        "user": UserSerializer(user).data,
        "access": access,
        "refresh": refresh,
        "access_token": access,
        "refresh_token": refresh,
        "tokens": tokens,
        "message": message,
    }


def _send_social_welcome_email(request, user, provider: str) -> None:
    """
    Send welcome email for first-time social users.
    This is best-effort and does not block authentication.
    """
    site_name = getattr(settings, "SITE_NAME", "CampusHub")
    frontend_url = get_frontend_base_url()
    try:
        EmailService.send_email(
            subject=f"Welcome to {site_name}!",
            message=(
                f"Welcome to {site_name}! Your account was created using {provider}.\n\n"
                + (
                    f"Start exploring here: {frontend_url}\n\n"
                    if frontend_url
                    else ""
                )
                + "You can now sign in and start using CampusHub."
            ),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send %s social welcome fallback email to %s",
            provider,
            getattr(user, "email", ""),
        )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _get_google_allowed_audiences() -> set[str]:
    return set(_split_csv(str(getattr(settings, "SOCIAL_AUTH_GOOGLE_CLIENT_ID", "") or "")))


def _is_valid_google_audience(audience: str | None) -> bool:
    allowed = _get_google_allowed_audiences()
    if not allowed:
        return True
    if not audience:
        return False
    return audience in allowed


def _fetch_google_userinfo_from_id_token(id_token: str) -> dict:
    response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError("Failed to verify Google ID token")
    payload = response.json() or {}
    if not _is_valid_google_audience(payload.get("aud")):
        raise ValueError("Google ID token has an invalid audience")
    return payload


def _fetch_google_userinfo_from_access_token(access_token: str) -> dict:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError("Failed to fetch Google user profile")
    return response.json() or {}


def _normalize_google_user_data(payload: dict) -> dict:
    email = str(payload.get("email") or "").strip().lower()
    full_name = str(payload.get("name") or "").strip()
    first_name = str(payload.get("given_name") or "").strip()
    last_name = str(payload.get("family_name") or "").strip()
    if not first_name and full_name:
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else last_name
    return {
        "email": email,
        "name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "picture": payload.get("picture") or "",
        "sub": payload.get("sub") or payload.get("id") or "",
    }


def _fetch_microsoft_userinfo(access_token: str) -> dict:
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError("Failed to fetch Microsoft user profile")
    return response.json() or {}


def _attach_microsoft_photo(access_token: str, payload: dict) -> None:
    try:
        photo_response = requests.get(
            "https://graph.microsoft.com/v1.0/me/photo/$value",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=8,
        )
        if photo_response.status_code == 200 and photo_response.content:
            payload["photo_content"] = photo_response.content
            payload["photo_content_type"] = photo_response.headers.get("Content-Type", "")
    except Exception:
        return


class GoogleOAuthView(APIView):
    """
    Google OAuth2 authentication endpoint.

    POST /api/auth/google/
    Body: { "code": "authorization_code" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        code = request.data.get("code")

        if not code:
            return Response(
                {"error": "Authorization code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get provider config
            config = get_google_provider_config()
            redirect_uri = _resolve_redirect_uri(request, config["redirect_uri"])

            # Exchange code for tokens
            token_response = requests.post(
                config["token_url"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

            if token_response.status_code != 200:
                return Response(
                    {"error": "Failed to exchange code for tokens"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            access_token = token_response.json().get("access_token")

            # Get user info
            userinfo_response = requests.get(
                config["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_response.status_code != 200:
                return Response(
                    {"error": "Failed to get user info"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            google_user_data = userinfo_response.json()
            google_email = str(google_user_data.get("email") or "").strip().lower()
            is_new_social_user = bool(
                google_email and not User.objects.filter(email=google_email).exists()
            )

            # Process user
            user = SocialAuthService.process_google_user(google_user_data)
            if is_new_social_user:
                _send_social_welcome_email(request, user, "Google")

            # Generate tokens
            tokens = SocialAuthService.generate_tokens_for_social_user(user)
            user.update_last_login()

            from .signals import log_user_activity
            from .views import _is_suspicious_login, _send_suspicious_login_alert

            try:
                from apps.gamification.services import GamificationService

                GamificationService.record_login(user)
            except Exception:
                logger.exception(
                    "Failed to record Google OAuth login gamification for user_id=%s",
                    user.id,
                )
            if _is_suspicious_login(user, request):
                _send_suspicious_login_alert(user, request)
            log_user_activity(user, "login", "User logged in via Google OAuth", request)

            return Response(
                _build_auth_success_payload(
                    user,
                    tokens,
                    "Google authentication successful",
                )
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MicrosoftOAuthView(APIView):
    """
    Microsoft OAuth2 authentication endpoint.

    POST /api/auth/microsoft/
    Body: { "code": "authorization_code" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        code = request.data.get("code")

        if not code:
            return Response(
                {"error": "Authorization code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get provider config
            config = get_microsoft_provider_config()
            redirect_uri = _resolve_redirect_uri(request, config["redirect_uri"])

            # Exchange code for tokens
            token_response = requests.post(
                config["token_url"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "scope": config["scope"],
                },
            )

            if token_response.status_code != 200:
                return Response(
                    {"error": "Failed to exchange code for tokens"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            access_token = token_response.json().get("access_token")

            # Get user info
            userinfo_response = requests.get(
                config["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_response.status_code != 200:
                return Response(
                    {"error": "Failed to get user info"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            microsoft_user_data = userinfo_response.json()
            microsoft_email = str(
                microsoft_user_data.get("email")
                or microsoft_user_data.get("mail")
                or microsoft_user_data.get("userPrincipalName")
                or ""
            ).strip().lower()
            is_new_social_user = bool(
                microsoft_email
                and not User.objects.filter(email=microsoft_email).exists()
            )

            # Best-effort profile photo fetch.
            photo_response = requests.get(
                "https://graph.microsoft.com/v1.0/me/photo/$value",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if photo_response.status_code == 200 and photo_response.content:
                microsoft_user_data["photo_content"] = photo_response.content
                microsoft_user_data["photo_content_type"] = photo_response.headers.get(
                    "Content-Type", ""
                )

            # Process user
            user = SocialAuthService.process_microsoft_user(microsoft_user_data)
            if is_new_social_user:
                _send_social_welcome_email(request, user, "Microsoft")

            # Generate tokens
            tokens = SocialAuthService.generate_tokens_for_social_user(user)
            user.update_last_login()

            from .signals import log_user_activity
            from .views import _is_suspicious_login, _send_suspicious_login_alert

            try:
                from apps.gamification.services import GamificationService

                GamificationService.record_login(user)
            except Exception:
                logger.exception(
                    "Failed to record Microsoft OAuth login gamification for user_id=%s",
                    user.id,
                )
            if _is_suspicious_login(user, request):
                _send_suspicious_login_alert(user, request)
            log_user_activity(
                user,
                "login",
                "User logged in via Microsoft OAuth",
                request,
            )

            return Response(
                _build_auth_success_payload(
                    user,
                    tokens,
                    "Microsoft authentication successful",
                )
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GoogleOAuthNativeView(APIView):
    """
    Google native authentication endpoint for mobile SDKs.

    POST /api/auth/google/native/
    Body: { "id_token": "...", "access_token": "..." }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        id_token = (
            request.data.get("id_token")
            or request.data.get("idToken")
            or request.data.get("token")
        )
        access_token = request.data.get("access_token") or request.data.get(
            "accessToken"
        )

        if not id_token and not access_token:
            return Response(
                {"error": "ID token or access token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = {}
            if id_token:
                payload = _fetch_google_userinfo_from_id_token(id_token)
            if not payload and access_token:
                payload = _fetch_google_userinfo_from_access_token(access_token)

            google_user_data = _normalize_google_user_data(payload)
            google_email = google_user_data.get("email", "")
            if not google_email:
                return Response(
                    {"error": "Google profile did not include an email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_new_social_user = bool(
                google_email and not User.objects.filter(email=google_email).exists()
            )

            user = SocialAuthService.process_google_user(google_user_data)
            if is_new_social_user:
                _send_social_welcome_email(request, user, "Google")

            tokens = SocialAuthService.generate_tokens_for_social_user(user)
            user.update_last_login()

            from .signals import log_user_activity
            from .views import _is_suspicious_login, _send_suspicious_login_alert

            try:
                from apps.gamification.services import GamificationService

                GamificationService.record_login(user)
            except Exception:
                logger.exception(
                    "Failed to record Google native login gamification for user_id=%s",
                    user.id,
                )
            if _is_suspicious_login(user, request):
                _send_suspicious_login_alert(user, request)
            log_user_activity(
                user,
                "login",
                "User logged in via Google native auth",
                request,
            )

            return Response(
                _build_auth_success_payload(
                    user,
                    tokens,
                    "Google authentication successful",
                )
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class MicrosoftOAuthNativeView(APIView):
    """
    Microsoft native authentication endpoint for mobile SDKs.

    POST /api/auth/microsoft/native/
    Body: { "access_token": "...", "id_token": "..." }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get("access_token") or request.data.get(
            "accessToken"
        )

        if not access_token:
            return Response(
                {"error": "Access token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            microsoft_user_data = _fetch_microsoft_userinfo(access_token)
            _attach_microsoft_photo(access_token, microsoft_user_data)

            microsoft_email = str(
                microsoft_user_data.get("email")
                or microsoft_user_data.get("mail")
                or microsoft_user_data.get("userPrincipalName")
                or ""
            ).strip().lower()
            if not microsoft_email:
                return Response(
                    {"error": "Microsoft profile did not include an email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_new_social_user = bool(
                microsoft_email
                and not User.objects.filter(email=microsoft_email).exists()
            )

            user = SocialAuthService.process_microsoft_user(microsoft_user_data)
            if is_new_social_user:
                _send_social_welcome_email(request, user, "Microsoft")

            tokens = SocialAuthService.generate_tokens_for_social_user(user)
            user.update_last_login()

            from .signals import log_user_activity
            from .views import _is_suspicious_login, _send_suspicious_login_alert

            try:
                from apps.gamification.services import GamificationService

                GamificationService.record_login(user)
            except Exception:
                logger.exception(
                    "Failed to record Microsoft native login gamification for user_id=%s",
                    user.id,
                )
            if _is_suspicious_login(user, request):
                _send_suspicious_login_alert(user, request)
            log_user_activity(
                user,
                "login",
                "User logged in via Microsoft native auth",
                request,
            )

            return Response(
                _build_auth_success_payload(
                    user,
                    tokens,
                    "Microsoft authentication successful",
                )
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class GoogleOAuthUrlView(APIView):
    """
    Get Google OAuth authorization URL.

    GET /api/auth/google/url/
    """

    permission_classes = [AllowAny]

    def get(self, request):
        config = get_google_provider_config()
        redirect_uri = _resolve_redirect_uri(request, config["redirect_uri"])

        # Build authorization URL
        from urllib.parse import urlencode

        params = {
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": config["scope"],
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{config['auth_url']}?{urlencode(params)}"

        return Response({"authorization_url": auth_url})


class GoogleOAuthCallbackView(APIView):
    """
    OAuth callback bridge for mobile clients.

    GET /api/auth/google/callback/
    """

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")
        state = request.query_params.get("state")
        callback_url = _build_mobile_callback_url(
            "google",
            {
                "code": code,
                "error": error,
                "error_description": error_description,
                "state": state,
            },
        )
        return MobileHttpResponseRedirect(callback_url)


class MicrosoftOAuthUrlView(APIView):
    """
    Get Microsoft OAuth authorization URL.

    GET /api/auth/microsoft/url/
    """

    permission_classes = [AllowAny]

    def get(self, request):
        config = get_microsoft_provider_config()
        redirect_uri = _resolve_redirect_uri(request, config["redirect_uri"])

        # Build authorization URL
        from urllib.parse import urlencode

        params = {
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": config["scope"],
            "response_mode": "query",
        }

        auth_url = f"{config['auth_url']}?{urlencode(params)}"

        return Response({"authorization_url": auth_url})


class MicrosoftOAuthCallbackView(APIView):
    """
    OAuth callback bridge for mobile clients.

    GET /api/auth/microsoft/callback/
    """

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")
        state = request.query_params.get("state")
        callback_url = _build_mobile_callback_url(
            "microsoft",
            {
                "code": code,
                "error": error,
                "error_description": error_description,
                "state": state,
            },
        )
        return MobileHttpResponseRedirect(callback_url)


class GoogleOAuthLinkView(APIView):
    """
    Link a Google account to the currently authenticated user.

    POST /api/auth/google/link/
    Body: { "id_token": "...", "access_token": "..." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        id_token = request.data.get("id_token")
        access_token = request.data.get("access_token")

        if not id_token and not access_token:
            return Response(
                {"detail": "id_token or access_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if id_token:
                payload = _fetch_google_userinfo_from_id_token(id_token)
            else:
                payload = _fetch_google_userinfo_from_access_token(access_token)

            google_user_data = _normalize_google_user_data(payload)
            provider_user_id = str(google_user_data.get("sub") or "")
            provider_email = str(google_user_data.get("email") or "").strip().lower()

            if not provider_user_id:
                return Response(
                    {"detail": "Unable to identify Google account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from .models import LinkedAccount
            from .services import LinkedAccountService

            conflict = LinkedAccount.objects.filter(
                provider="google",
                provider_user_id=provider_user_id,
            ).exclude(user=request.user)

            if conflict.exists():
                return Response(
                    {"detail": "This Google account is linked to another user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            LinkedAccountService.link_account(
                user=request.user,
                provider="google",
                provider_user_id=provider_user_id,
                provider_email=provider_email,
            )

            return Response({"message": "Google account linked successfully."})
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )


class MicrosoftOAuthLinkView(APIView):
    """
    Link a Microsoft account to the currently authenticated user.

    POST /api/auth/microsoft/link/
    Body: { "access_token": "..." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        access_token = request.data.get("access_token")
        if not access_token:
            return Response(
                {"detail": "access_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            microsoft_user_data = _fetch_microsoft_userinfo(access_token)
            provider_user_id = str(microsoft_user_data.get("id") or "")
            provider_email = str(
                microsoft_user_data.get("mail")
                or microsoft_user_data.get("userPrincipalName")
                or ""
            ).strip().lower()

            if not provider_user_id:
                return Response(
                    {"detail": "Unable to identify Microsoft account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from .models import LinkedAccount
            from .services import LinkedAccountService

            conflict = LinkedAccount.objects.filter(
                provider="microsoft",
                provider_user_id=provider_user_id,
            ).exclude(user=request.user)

            if conflict.exists():
                return Response(
                    {"detail": "This Microsoft account is linked to another user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            LinkedAccountService.link_account(
                user=request.user,
                provider="microsoft",
                provider_user_id=provider_user_id,
                provider_email=provider_email,
            )

            return Response({"message": "Microsoft account linked successfully."})
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
