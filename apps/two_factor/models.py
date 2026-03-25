"""
Two-Factor Authentication models for CampusHub.
"""

import secrets

import pyotp
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.core.encryption import (EncryptedFieldMixin, encrypted_charfield,
                                  encrypted_jsonfield)

User = get_user_model()


class TwoFactorSetting(EncryptedFieldMixin, models.Model):
    """
    Stores 2FA settings for users.
    """

    METHOD_CHOICES = [
        ("totp", "Authenticator App (TOTP)"),
        ("email", "Email Verification"),
        ("sms", "SMS Verification"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="two_factor_settings"
    )
    enabled = models.BooleanField(default=False)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="totp")
    totp_secret = encrypted_charfield(max_length=128, blank=True)
    backup_codes = encrypted_jsonfield(default=list, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "two_factor"
        verbose_name = "Two-Factor Setting"
        verbose_name_plural = "Two-Factor Settings"

    def __str__(self):
        return f"2FA for {self.user.username}"

    def generate_totp_secret(self):
        """Generate a new TOTP secret."""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def get_totp_uri(self):
        """Get the TOTP URI for QR code generation."""
        if not self.totp_secret:
            self.generate_totp_secret()
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.user.email, issuer_name="CampusHub"
        )

    def verify_totp(self, code):
        """Verify a TOTP code."""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(code)

    def generate_backup_codes(self):
        """Generate backup codes for 2FA recovery."""
        codes = []
        for _ in range(10):
            code = secrets.token_hex(4).upper()
            codes.append({"code": code, "used": False})
        self.backup_codes = codes
        return codes

    def verify_backup_code(self, code):
        """Verify a backup code."""
        for item in self.backup_codes:
            if item["code"] == code.upper() and not item["used"]:
                item["used"] = True
                self.save()
                return True
        return False

    def disable(self):
        """Disable 2FA."""
        self.enabled = False
        self.totp_secret = ""
        self.backup_codes = []
        self.verified_at = None
        self.save()


class TwoFactorVerification(EncryptedFieldMixin, models.Model):
    """
    Stores pending 2FA verification attempts.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("expired", "Expired"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="two_factor_verifications"
    )
    code = encrypted_charfield(max_length=32)
    method = models.CharField(max_length=10)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "two_factor"
        verbose_name = "Two-Factor Verification"
        verbose_name_plural = "Two-Factor Verifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"2FA verification for {self.user.username}"

    @property
    def is_expired(self):
        """Check if the verification has expired."""
        return timezone.now() > self.expires_at

    def verify(self, code):
        """Verify the code."""
        if self.is_expired:
            self.status = "expired"
            self.save()
            return False

        if self.code == code:
            self.status = "verified"
            self.save()
            return True

        self.status = "failed"
        self.save()
        return False

    @classmethod
    def create_for_user(cls, user, method, ip_address=None, user_agent=None):
        """Create a new verification for a user."""
        # Generate random 6-digit code
        code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

        # Set expiration to 5 minutes
        expires_at = timezone.now() + timezone.timedelta(minutes=5)

        return cls.objects.create(
            user=user,
            code=code,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
