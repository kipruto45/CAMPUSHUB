"""
Magic link authentication for CampusHub.

This module provides:
- 15-minute signed magic-link tokens
- One-time-use token consumption with audit history
- Email and IP-based rate limiting
- Frontend/mobile deep-link generation
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .constants import EMAIL_NOT_VERIFIED_CODE, EMAIL_NOT_VERIFIED_MESSAGE
from apps.core.emails import EmailService

User = get_user_model()
logger = logging.getLogger(__name__)

MAGIC_LINK_SALT = "campushub.magic-link"
MAGIC_LINK_TTL_MINUTES = 15
MAGIC_LINK_TOKEN_VERSION = 1
MAGIC_LINK_RATE_WINDOW_MINUTES = 15
MAGIC_LINK_EMAIL_LIMIT = 5
MAGIC_LINK_IP_LIMIT = 10
MAGIC_LINK_HISTORY_RETENTION_HOURS = 24


@dataclass
class MagicLinkResult:
    """Result of a magic-link operation."""

    success: bool
    message: str
    code: Optional[str] = None
    token: Optional[str] = None
    access: Optional[str] = None
    refresh: Optional[str] = None
    user_id: Optional[int] = None
    email: Optional[str] = None
    expires_at: Optional[datetime] = None


class RateLimiter:
    """
    Cache-backed rate limiter for magic-link requests.
    """

    def __init__(self, prefix: str, max_requests: int, window_minutes: int):
        self.prefix = prefix
        self.max_requests = max_requests
        self.window_minutes = window_minutes

    def _cache_key(self, identifier: str) -> str:
        normalized = str(identifier or "").strip().lower()
        return f"magic_link_ratelimit:{self.prefix}:{normalized}"

    def is_allowed(self, identifier: str) -> Tuple[bool, int]:
        if not identifier:
            return True, self.max_requests

        cache_key = self._cache_key(identifier)
        now = timezone.now()
        cutoff = now - timedelta(minutes=self.window_minutes)
        attempts = cache.get(cache_key, [])
        attempts = [
            attempt for attempt in attempts
            if datetime.fromisoformat(attempt) > cutoff
        ]

        if len(attempts) >= self.max_requests:
            cache.set(cache_key, attempts, timeout=self.window_minutes * 60)
            return False, 0

        attempts.append(now.isoformat())
        cache.set(cache_key, attempts, timeout=self.window_minutes * 60)
        return True, max(0, self.max_requests - len(attempts))


class MagicLinkToken:
    """Signed token helper for magic-link auth."""

    def __init__(self, ttl_minutes: int = MAGIC_LINK_TTL_MINUTES):
        self.ttl_minutes = ttl_minutes

    def generate(self, user_id: int) -> Tuple[str, datetime]:
        expires_at = timezone.now() + timedelta(minutes=self.ttl_minutes)
        payload = {
            "user_id": user_id,
            "exp": expires_at.timestamp(),
            "v": MAGIC_LINK_TOKEN_VERSION,
            "nonce": secrets.token_hex(16),
        }
        return signing.dumps(payload, salt=MAGIC_LINK_SALT), expires_at

    def validate(self, token: str) -> dict:
        data = signing.loads(token, salt=MAGIC_LINK_SALT)
        expires_at = datetime.fromtimestamp(float(data.get("exp", 0)), tz=dt_timezone.utc)
        if timezone.now() > expires_at:
            raise SignatureExpired("Token has expired")
        if data.get("v") != MAGIC_LINK_TOKEN_VERSION:
            raise BadSignature("Invalid token version")
        return data


class UsedTokenTracker:
    """Persist consumed token hashes so magic links can only be used once."""

    @staticmethod
    def cleanup():
        from .models import MagicLinkTokenHistory

        cutoff = timezone.now() - timedelta(hours=MAGIC_LINK_HISTORY_RETENTION_HOURS)
        MagicLinkTokenHistory.objects.filter(used_at__lt=cutoff).delete()

    @staticmethod
    def mark_used(
        token_hash: str,
        user_id: int,
        ip_address: Optional[str] = None,
        user_agent: str = "",
    ) -> None:
        from .models import MagicLinkTokenHistory

        UsedTokenTracker.cleanup()
        MagicLinkTokenHistory.objects.create(
            token_hash=token_hash,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent or "",
        )

    @staticmethod
    def is_used(token_hash: str) -> bool:
        from .models import MagicLinkTokenHistory

        UsedTokenTracker.cleanup()
        return MagicLinkTokenHistory.objects.filter(token_hash=token_hash).exists()


class MagicLinkService:
    """Service for requesting and consuming magic links."""

    def __init__(self):
        self.token_handler = MagicLinkToken()
        self.email_rate_limiter = RateLimiter(
            prefix="email",
            max_requests=MAGIC_LINK_EMAIL_LIMIT,
            window_minutes=MAGIC_LINK_RATE_WINDOW_MINUTES,
        )
        self.ip_rate_limiter = RateLimiter(
            prefix="ip",
            max_requests=MAGIC_LINK_IP_LIMIT,
            window_minutes=MAGIC_LINK_RATE_WINDOW_MINUTES,
        )

    def _build_magic_link_url(
        self,
        token: str,
        request_base_url: Optional[str] = None,
    ) -> str:
        query = urlencode({"token": token})
        if request_base_url:
            consume_path = reverse("accounts:magic-link-consume")
            return f"{str(request_base_url).rstrip('/')}{consume_path}?{query}"

        frontend_base = (
            str(getattr(settings, "FRONTEND_URL", "") or "").strip()
            or str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
            or str(getattr(settings, "WEB_APP_URL", "") or "").strip()
        ).rstrip("/")

        if frontend_base:
            return f"{frontend_base}/magic-link?{query}"

        deeplink_scheme = str(
            getattr(settings, "MOBILE_DEEPLINK_SCHEME", "") or ""
        ).strip()
        if deeplink_scheme:
            return f"{deeplink_scheme}://magic-link?{query}"

        return f"https://campushub.app/magic-link?{query}"

    def _send_magic_link_email(
        self,
        user: User,
        magic_link: str,
        expires_at: datetime,
    ) -> None:
        first_name = str(getattr(user, "first_name", "") or "").strip()
        greeting_name = first_name or user.email
        expiry_minutes = max(
            1,
            int((expires_at - timezone.now()).total_seconds() // 60) or MAGIC_LINK_TTL_MINUTES,
        )
        plain_text = (
            f"Hi {greeting_name},\n\n"
            "Use the secure link below to sign in to CampusHub:\n"
            f"{magic_link}\n\n"
            f"This link works for about {expiry_minutes} minutes and can only be used once.\n\n"
            "The link opens a CampusHub sign-in screen where you can continue on web, open the app, or copy the token if needed.\n\n"
            "If you did not request this email, you can safely ignore it."
        )
        EmailService.send_email(
            subject="Your CampusHub Magic Link",
            message=plain_text,
            recipient_list=[user.email],
        )

    def request_magic_link(
        self,
        email: str,
        ip_address: Optional[str] = None,
        request_base_url: Optional[str] = None,
    ) -> MagicLinkResult:
        email = str(email or "").lower().strip()
        if not email:
            return MagicLinkResult(success=False, message="Email is required.")

        email_allowed, _ = self.email_rate_limiter.is_allowed(email)
        ip_allowed, _ = self.ip_rate_limiter.is_allowed(ip_address or "")
        if not email_allowed or not ip_allowed:
            logger.warning(
                "Magic link rate limit exceeded for email=%s ip=%s",
                email,
                ip_address,
            )
            return MagicLinkResult(
                success=False,
                message="Too many magic link requests. Please try again later.",
            )

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            return MagicLinkResult(
                success=True,
                message="If an account exists with this email, a magic link will be sent.",
            )

        try:
            token, expires_at = self.token_handler.generate(user.id)
            magic_link = self._build_magic_link_url(
                token,
                request_base_url=request_base_url,
            )
            self._send_magic_link_email(user, magic_link, expires_at)
        except Exception as exc:
            logger.error("Error sending magic link for %s: %s", email, exc)
            return MagicLinkResult(
                success=False,
                message="Failed to send magic link. Please try again.",
            )

        logger.info("Magic link sent to %s", email)
        return MagicLinkResult(
            success=True,
            message="If an account exists with this email, a magic link will be sent.",
            token=token[:20] + "...",
            user_id=user.id,
            expires_at=expires_at,
        )

    def consume_magic_link(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: str = "",
    ) -> MagicLinkResult:
        token = str(token or "").strip()
        if not token:
            return MagicLinkResult(success=False, message="Token is required.")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if UsedTokenTracker.is_used(token_hash):
            logger.warning("Attempted reuse of magic link token")
            return MagicLinkResult(
                success=False,
                message="This magic link has already been used.",
            )

        try:
            payload = self.token_handler.validate(token)
        except SignatureExpired:
            return MagicLinkResult(
                success=False,
                message="This magic link has expired. Please request a new one.",
            )
        except BadSignature as exc:
            logger.warning("Invalid magic link token: %s", exc)
            return MagicLinkResult(success=False, message="Invalid magic link.")

        user = User.objects.filter(id=payload.get("user_id"), is_active=True).first()
        if not user:
            return MagicLinkResult(success=False, message="User not found.")
        if not user.is_verified:
            return MagicLinkResult(
                success=False,
                message=EMAIL_NOT_VERIFIED_MESSAGE,
                code=EMAIL_NOT_VERIFIED_CODE,
                user_id=user.id,
                email=user.email,
            )

        try:
            with transaction.atomic():
                if UsedTokenTracker.is_used(token_hash):
                    return MagicLinkResult(
                        success=False,
                        message="This magic link has already been used.",
                    )
                UsedTokenTracker.mark_used(
                    token_hash=token_hash,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except Exception as exc:
            logger.error("Failed to mark magic link token as used: %s", exc)
            return MagicLinkResult(
                success=False,
                message="Unable to verify this magic link right now.",
            )

        try:
            refresh = RefreshToken.for_user(user)
        except Exception as exc:
            logger.error("Failed to generate JWTs from magic link: %s", exc)
            return MagicLinkResult(
                success=False,
                message="Failed to generate authentication tokens.",
            )

        return MagicLinkResult(
            success=True,
            message="Successfully authenticated with magic link.",
            access=str(refresh.access_token),
            refresh=str(refresh),
            user_id=user.id,
            email=user.email,
        )

    def resend_rate_limit_check(self, email: str) -> Tuple[bool, str]:
        is_allowed, remaining = self.email_rate_limiter.is_allowed(email)
        if not is_allowed:
            return False, "Please wait before requesting another magic link."
        return True, f"{remaining} attempts remaining"


magic_link_service = MagicLinkService()
