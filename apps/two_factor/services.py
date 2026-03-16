"""
Two-Factor Authentication service for CampusHub.
"""

from typing import Any, Optional, Tuple

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TwoFactorService:
    """
    Service for handling Two-Factor Authentication operations.
    """

    @staticmethod
    def setup_2fa_for_user(user, method: str = "totp") -> Tuple[bool, dict]:
        """
        Set up 2FA for a user.

        Args:
            user: User instance
            method: 2FA method ('totp', 'email', 'sms')

        Returns:
            Tuple of (success, data)
        """
        from apps.two_factor.models import TwoFactorSetting

        # Get or create 2FA settings
        settings, created = TwoFactorSetting.objects.get_or_create(user=user)

        if method == "totp":
            # Generate TOTP secret
            secret = settings.generate_totp_secret()
            settings.method = "totp"
            settings.save()

            return True, {
                "secret": secret,
                "uri": settings.get_totp_uri(),
                "message": "Scan the QR code with your authenticator app",
            }

        elif method == "email":
            settings.method = "email"
            settings.save()

            # Send verification email
            verification = TwoFactorService.send_email_verification(user)

            return True, {
                "verification_id": verification.id,
                "message": "Check your email for the verification code",
            }

        return False, {"error": "Invalid method"}

    @staticmethod
    def verify_2fa_code(user, code: str) -> bool:
        """
        Verify a 2FA code.

        Args:
            user: User instance
            code: Verification code

        Returns:
            True if verification successful
        """
        from apps.two_factor.models import (TwoFactorSetting,
                                            TwoFactorVerification)

        try:
            settings = TwoFactorSetting.objects.get(user=user)

            if not settings.enabled:
                return True  # 2FA not enabled, allow login

            # Try TOTP first
            if settings.method == "totp":
                return settings.verify_totp(code)

            # Try backup codes
            if settings.verify_backup_code(code):
                return True

            # Try email verification
            if settings.method == "email":
                # Check for pending verification
                verification = TwoFactorVerification.objects.filter(
                    user=user, status="pending"
                ).first()

                if verification and verification.verify(code):
                    return True

            return False

        except TwoFactorSetting.DoesNotExist:
            return True  # No 2FA set up

    @staticmethod
    def enable_2fa(user, verified_code: str) -> Tuple[bool, str]:
        """
        Enable 2FA after verification.

        Args:
            user: User instance
            verified_code: Verified code from setup

        Returns:
            Tuple of (success, message)
        """
        from apps.two_factor.models import TwoFactorSetting

        try:
            settings = TwoFactorSetting.objects.get(user=user)

            # Verify the code
            if settings.method == "totp":
                if not settings.verify_totp(verified_code):
                    return False, "Invalid verification code"
            else:
                return False, "Invalid method"

            # Generate backup codes
            backup_codes = settings.generate_backup_codes()

            # Enable 2FA
            settings.enabled = True
            settings.verified_at = timezone.now()
            settings.save()

            # Return backup codes
            codes_list = [item["code"] for item in backup_codes]

            return True, f'2FA enabled. Backup codes: {", ".join(codes_list[:5])}...'

        except TwoFactorSetting.DoesNotExist:
            return False, "2FA not set up"

    @staticmethod
    def disable_2fa(user, password: str) -> Tuple[bool, str]:
        """
        Disable 2FA for a user.

        Args:
            user: User instance
            password: User's password for verification

        Returns:
            Tuple of (success, message)
        """
        from apps.two_factor.models import TwoFactorSetting

        # Verify password
        if not user.check_password(password):
            return False, "Invalid password"

        try:
            settings = TwoFactorSetting.objects.get(user=user)
            settings.disable()
            return True, "2FA disabled successfully"
        except TwoFactorSetting.DoesNotExist:
            return False, "2FA not enabled"

    @staticmethod
    def send_email_verification(user) -> Optional[Any]:
        """
        Send email verification for 2FA.

        Args:
            user: User instance

        Returns:
            TwoFactorVerification instance
        """
        from apps.two_factor.models import TwoFactorVerification

        # Create verification
        verification = TwoFactorVerification.create_for_user(user=user, method="email")

        # Send email with code
        from apps.core.emails import EmailService

        EmailService.send_email(
            subject="Your CampusHub 2FA Code",
            message=f"Your verification code is: {verification.code}",
            recipient_list=[user.email],
        )

        return verification

    @staticmethod
    def get_2fa_status(user) -> dict:
        """
        Get 2FA status for a user.

        Args:
            user: User instance

        Returns:
            Dictionary with 2FA status
        """
        from apps.two_factor.models import TwoFactorSetting

        try:
            settings = TwoFactorSetting.objects.get(user=user)
            return {
                "enabled": settings.enabled,
                "method": settings.method,
                "verified_at": settings.verified_at,
            }
        except TwoFactorSetting.DoesNotExist:
            return {
                "enabled": False,
                "method": None,
                "verified_at": None,
            }

    @staticmethod
    def is_2fa_required(user) -> bool:
        """
        Check if 2FA is required for a user.

        Args:
            user: User instance

        Returns:
            True if 2FA is required
        """
        return TwoFactorService.get_2fa_status(user)["enabled"]
