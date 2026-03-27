"""
Social authentication service for Google and Microsoft OAuth2.
"""

import logging
from urllib.parse import urlparse

import requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction

from .services import LinkedAccountService

User = get_user_model()
logger = logging.getLogger(__name__)


class SocialAuthService:
    """Service for handling social authentication."""

    IMAGE_CONTENT_TYPES = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }

    @staticmethod
    def _is_cloudinary_authorization_error(exc: Exception) -> bool:
        """Return True when Cloudinary rejects an upload for authorization reasons."""
        try:
            from cloudinary.exceptions import AuthorizationRequired
        except Exception:
            return False
        return isinstance(exc, AuthorizationRequired)

    @staticmethod
    def _import_profile_image(
        user,
        provider: str,
        image_url: str = "",
        image_bytes: bytes | None = None,
        content_type: str = "",
    ):
        """
        Download and save provider profile image when possible.

        This is best-effort and intentionally silent on failures.
        """
        if not image_url and not image_bytes:
            return

        # Avoid repeated writes when a non-default image already exists.
        existing_image = getattr(user, "profile_image", None)
        existing_name = str(getattr(existing_image, "name", "") or "").strip()
        default_name = str(
            getattr(user._meta.get_field("profile_image"), "default", "") or ""
        ).strip()
        if existing_name and existing_name != default_name:
            return

        try:
            if image_bytes:
                content = image_bytes
            else:
                response = requests.get(image_url, timeout=8)
                if response.status_code != 200:
                    return
                content = response.content or b""
                content_type = response.headers.get(
                    "Content-Type",
                    content_type,
                )

            content_type = (content_type or "").split(";")[0].strip().lower()
            extension = SocialAuthService.IMAGE_CONTENT_TYPES.get(content_type)

            if not extension:
                path = urlparse(image_url).path.lower() if image_url else ""
                for candidate in ("jpg", "jpeg", "png", "webp", "gif"):
                    if path.endswith(f".{candidate}"):
                        extension = "jpg" if candidate == "jpeg" else candidate
                        break
            if not extension:
                extension = "jpg"

            if not content or len(content) > 5 * 1024 * 1024:
                return

            filename = f"{provider}_{user.id}.{extension}"
            try:
                user.profile_image.save(filename, ContentFile(content), save=True)
            except Exception as exc:
                if SocialAuthService._is_cloudinary_authorization_error(exc):
                    logger.warning(
                        "Skipping %s profile image import for %s because cloud storage rejected the upload: %s",
                        provider,
                        user.email,
                        exc,
                    )
                    return
                raise
        except Exception:
            logger.exception(
                "Failed to import %s profile image for %s",
                provider,
                user.email,
            )

    @staticmethod
    @transaction.atomic
    def process_google_user(google_user_data):
        """
        Process Google OAuth2 user data and create/update user.

        Args:
            google_user_data: Dict containing:
                - email: User's email
                - name: User's full name
                - first_name: First name
                - last_name: Last name
                - picture: Profile picture URL
                - sub: Google user ID

        Returns:
            User instance
        """
        email = google_user_data.get("email")

        if not email:
            raise ValueError("Email is required from Google OAuth")

        # Check if user exists
        user = User.objects.filter(email=email).first()

        if user:
            # Update existing user
            user.first_name = google_user_data.get(
                "first_name",
                user.first_name,
            )
            user.last_name = google_user_data.get("last_name", user.last_name)
            if google_user_data.get("name"):
                user.full_name = google_user_data.get("name")
            if user.auth_provider != "email":
                user.auth_provider = "google"
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "full_name",
                    "auth_provider",
                    "updated_at",
                ]
            )
            SocialAuthService._import_profile_image(
                user=user,
                provider="google",
                image_url=google_user_data.get("picture", ""),
            )
            logger.info(f"Updated Google user: {user.email}")
        else:
            # Create new user
            name_parts = google_user_data.get("name", "").split(" ", 1)
            user = User.objects.create_user(
                email=email,
                password=None,  # OAuth users don't have passwords
                full_name=google_user_data.get("name", ""),
                first_name=google_user_data.get(
                    "first_name", name_parts[0] if name_parts else ""
                ),
                last_name=name_parts[1] if len(name_parts) > 1 else "",
                is_verified=True,  # Google verifies email
                auth_provider="google",
            )

            # Create profile
            from .models import Profile

            Profile.objects.get_or_create(user=user)
            SocialAuthService._import_profile_image(
                user=user,
                provider="google",
                image_url=google_user_data.get("picture", ""),
            )

            logger.info(f"Created new Google user: {user.email}")

        provider_user_id = str(google_user_data.get("sub") or "")
        if provider_user_id:
            LinkedAccountService.link_account(
                user=user,
                provider="google",
                provider_user_id=provider_user_id,
                provider_email=email,
            )

        return user

    @staticmethod
    @transaction.atomic
    def process_microsoft_user(microsoft_user_data):
        """
        Process Microsoft OAuth2 user data and create/update user.

        Args:
            microsoft_user_data: Dict containing:
                - email: User's email
                - displayName: User's display name
                - givenName: First name
                - surname: Last name
                - id: Microsoft user ID

        Returns:
            User instance
        """
        email = (
            microsoft_user_data.get("email")
            or microsoft_user_data.get("mail")
            or microsoft_user_data.get("userPrincipalName")
        )

        if not email:
            raise ValueError("Email is required from Microsoft OAuth")

        # Check if user exists
        user = User.objects.filter(email=email).first()

        if user:
            # Update existing user
            user.first_name = microsoft_user_data.get(
                "givenName",
                user.first_name,
            )
            user.last_name = microsoft_user_data.get("surname", user.last_name)
            if microsoft_user_data.get("displayName"):
                user.full_name = microsoft_user_data.get("displayName")
            if user.auth_provider != "email":
                user.auth_provider = "microsoft"
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "full_name",
                    "auth_provider",
                    "updated_at",
                ]
            )
            SocialAuthService._import_profile_image(
                user=user,
                provider="microsoft",
                image_url=microsoft_user_data.get("photo", ""),
                image_bytes=microsoft_user_data.get("photo_content"),
                content_type=microsoft_user_data.get("photo_content_type", ""),
            )
            logger.info(f"Updated Microsoft user: {user.email}")
        else:
            # Create new user
            display_name = microsoft_user_data.get("displayName", "")
            name_parts = display_name.split(" ", 1)

            user = User.objects.create_user(
                email=email,
                password=None,
                full_name=display_name,
                first_name=microsoft_user_data.get(
                    "givenName", name_parts[0] if name_parts else ""
                ),
                last_name=name_parts[1] if len(name_parts) > 1 else "",
                is_verified=True,  # Microsoft verifies email
                auth_provider="microsoft",
            )

            # Create profile
            from .models import Profile

            Profile.objects.get_or_create(user=user)
            SocialAuthService._import_profile_image(
                user=user,
                provider="microsoft",
                image_url=microsoft_user_data.get("photo", ""),
                image_bytes=microsoft_user_data.get("photo_content"),
                content_type=microsoft_user_data.get("photo_content_type", ""),
            )

            logger.info(f"Created new Microsoft user: {user.email}")

        provider_user_id = str(microsoft_user_data.get("id") or "")
        if provider_user_id:
            LinkedAccountService.link_account(
                user=user,
                provider="microsoft",
                provider_user_id=provider_user_id,
                provider_email=email,
            )

        return user

    @staticmethod
    def generate_tokens_for_social_user(user):
        """
        Generate JWT tokens for OAuth user.

        Args:
            user: User instance

        Returns:
            Dict with access and refresh tokens
        """
        from .authentication import generate_tokens_for_user

        # Social logins always use the 30-day "remember me" session
        return generate_tokens_for_user(user, remember_me=True)


def get_google_provider_config():
    """Get Google OAuth configuration."""
    from django.conf import settings

    def _primary_google_client_id(raw_value: str) -> str:
        if not raw_value:
            return ""
        parts = [item.strip() for item in str(raw_value).split(",") if item.strip()]
        return parts[0] if parts else ""

    return {
        "client_id": _primary_google_client_id(
            settings.SOCIAL_AUTH_GOOGLE_CLIENT_ID
        ),
        "client_secret": settings.SOCIAL_AUTH_GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.SOCIAL_AUTH_GOOGLE_REDIRECT_URI,
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    }


def get_microsoft_provider_config():
    """Get Microsoft OAuth configuration."""
    from django.conf import settings

    tenant = getattr(settings, "SOCIAL_AUTH_MICROSOFT_TENANT_ID", "common") or "common"

    return {
        "client_id": settings.SOCIAL_AUTH_MICROSOFT_CLIENT_ID,
        "client_secret": settings.SOCIAL_AUTH_MICROSOFT_CLIENT_SECRET,
        "redirect_uri": settings.SOCIAL_AUTH_MICROSOFT_REDIRECT_URI,
        "auth_url": (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        ),
        "token_url": (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        ),
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile User.Read",
    }
