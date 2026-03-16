"""
Email verification models and utilities.
"""

import hashlib
import uuid

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

User = get_user_model()

EMAIL_VERIFY_SALT = "accounts.email.verify"
PASSWORD_RESET_SALT = "accounts.password.reset"


class EmailVerificationToken(models.Model):
    """Token for email verification."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="verification_tokens"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Email Verification Token"
        verbose_name_plural = "Email Verification Tokens"

    def __str__(self):
        return f"Verification token for {self.user.email}"

    def is_valid(self):
        """Check if token is valid."""
        return not self.is_used and self.expires_at > timezone.now()

    @classmethod
    def generate_token(cls, user):
        """Generate a new verification token."""
        # Generate unique token
        token_str = f"{user.email}{uuid.uuid4()}"
        token = hashlib.sha256(token_str.encode()).hexdigest()[:64]

        # Set expiry (24 hours)
        expires_at = timezone.now() + timezone.timedelta(hours=24)

        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    def get_verification_url(self, domain):
        """Get the verification URL."""
        return f"https://{domain}/api/auth/verify-email/{self.token}/"


class PasswordResetToken(models.Model):
    """Token for password reset."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def __str__(self):
        return f"Password reset token for {self.user.email}"

    def is_valid(self):
        """Check if token is valid."""
        return not self.is_used and self.expires_at > timezone.now()

    @classmethod
    def generate_token(cls, user):
        """Generate a new password reset token."""
        token_str = f"{user.email}{uuid.uuid4()}{timezone.now()}"
        token = hashlib.sha256(token_str.encode()).hexdigest()[:64]

        # Set expiry (1 hour)
        expires_at = timezone.now() + timezone.timedelta(hours=1)

        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    def get_reset_url(self, domain):
        """Get the password reset URL."""
        return f"https://{domain}/api/auth/password/reset/confirm/{self.token}/"


def generate_signed_verification_token(user):
    """Generate stateless signed verification token."""
    payload = {
        "user_id": str(user.id),
        "email": user.email,
    }
    return signing.dumps(payload, salt=EMAIL_VERIFY_SALT)


def validate_signed_verification_token(token, max_age_seconds=24 * 3600):
    """Validate stateless verification token and return user if valid."""
    try:
        payload = signing.loads(token, salt=EMAIL_VERIFY_SALT, max_age=max_age_seconds)
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None

    user_id = payload.get("user_id")
    email = payload.get("email")
    if not user_id or not email:
        return None

    try:
        return User.objects.filter(id=user_id, email=email, is_active=True).first()
    except ObjectDoesNotExist:
        return None


def generate_signed_password_reset_token(user):
    """Generate stateless signed password reset token."""
    payload = {
        "user_id": str(user.id),
        "email": user.email,
        "ts": timezone.now().timestamp(),
    }
    return signing.dumps(payload, salt=PASSWORD_RESET_SALT)


def validate_signed_password_reset_token(token, max_age_seconds=3600):
    """Validate stateless reset token and return user if valid."""
    try:
        payload = signing.loads(
            token, salt=PASSWORD_RESET_SALT, max_age=max_age_seconds
        )
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None

    user_id = payload.get("user_id")
    email = payload.get("email")
    if not user_id or not email:
        return None

    try:
        return User.objects.filter(id=user_id, email=email, is_active=True).first()
    except ObjectDoesNotExist:
        return None
