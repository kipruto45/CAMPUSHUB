"""
Profile services for handling profile-related business logic.
"""

import re
from datetime import timezone as datetime_timezone

from django.db.models import Count


class ProfileCompletionService:
    """Service for calculating profile completion percentage."""

    # Required fields for completion calculation
    REQUIRED_FIELDS = [
        "profile_image",
        "phone_number",
        "registration_number",
        "faculty",
        "department",
        "course",
        "year_of_study",
    ]

    # Optional but encouraged fields
    OPTIONAL_FIELDS = [
        "semester",
    ]

    @classmethod
    def calculate_completion(cls, user):
        """
        Calculate profile completion percentage.

        Args:
            user: User instance

        Returns:
            dict: Completion details including percentage and missing fields
        """
        filled_fields = []
        missing_fields = []

        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            value = getattr(user, field, None)
            if value:
                filled_fields.append(field)
            else:
                missing_fields.append(field)

        # Check optional fields
        for field in cls.OPTIONAL_FIELDS:
            value = getattr(user, field, None)
            if value:
                filled_fields.append(field)

        # Calculate percentage
        total_required = len(cls.REQUIRED_FIELDS)
        filled_required = len([f for f in filled_fields if f in cls.REQUIRED_FIELDS])

        # Weighted calculation: required fields = 80%, optional = 20%
        required_weight = 0.8
        optional_weight = 0.2

        required_percentage = (
            (filled_required / total_required) * 100 if total_required > 0 else 0
        )
        optional_filled = len([f for f in filled_fields if f in cls.OPTIONAL_FIELDS])
        optional_percentage = (
            (optional_filled / len(cls.OPTIONAL_FIELDS)) * 100
            if cls.OPTIONAL_FIELDS
            else 100
        )

        overall_percentage = int(
            (required_percentage * required_weight)
            + (optional_percentage * optional_weight)
        )

        return {
            "percentage": overall_percentage,
            "filled_fields": filled_fields,
            "missing_fields": missing_fields,
            "total_required": total_required,
            "filled_required": filled_required,
            "is_complete": len(missing_fields) == 0,
        }

    @classmethod
    def get_incomplete_fields(cls, user):
        """
        Get list of incomplete required fields.

        Args:
            user: User instance

        Returns:
            list: List of missing field names
        """
        completion = cls.calculate_completion(user)
        return completion["missing_fields"]


class LinkedAccountService:
    """Service for managing linked social accounts."""

    @classmethod
    def get_linked_providers(cls, user):
        """
        Get list of linked providers for a user.

        Args:
            user: User instance

        Returns:
            list: List of linked provider names
        """
        from .models import LinkedAccount

        linked = LinkedAccount.objects.filter(user=user, is_active=True).values_list(
            "provider", flat=True
        )

        # Also check user's auth_provider
        if user.auth_provider != "email":
            if user.auth_provider not in linked:
                linked = list(linked) + [user.auth_provider]

        return list(linked)

    @classmethod
    def is_provider_linked(cls, user, provider):
        """
        Check if a provider is linked to the user's account.

        Args:
            user: User instance
            provider: Provider name ('google' or 'microsoft')

        Returns:
            bool: True if provider is linked
        """
        if user.auth_provider == provider:
            return True

        from .models import LinkedAccount

        return LinkedAccount.objects.filter(
            user=user, provider=provider, is_active=True
        ).exists()

    @classmethod
    def link_account(cls, user, provider, provider_user_id, provider_email):
        """
        Link a social account to the user.

        Args:
            user: User instance
            provider: Provider name
            provider_user_id: Provider's user ID
            provider_email: Provider's email

        Returns:
            LinkedAccount: The created linked account
        """
        from .models import LinkedAccount

        linked_account, created = LinkedAccount.objects.update_or_create(
            provider=provider,
            provider_user_id=provider_user_id,
            defaults={
                "user": user,
                "provider_email": provider_email,
                "is_active": True,
            },
        )

        return linked_account

    @classmethod
    def unlink_account(cls, user, provider):
        """
        Unlink a social account from the user.

        Args:
            user: User instance
            provider: Provider name

        Returns:
            bool: True if account was unlinked
        """
        from .models import LinkedAccount

        linked = LinkedAccount.objects.filter(user=user, provider=provider).first()

        if linked:
            linked.is_active = False
            linked.save()
            return True

        return False


def register_user_session(user, request, refresh_token: str | None) -> str | None:
    """Create or update a tracked user session for JWT refresh tokens."""
    if not refresh_token:
        return None

    try:
        from django.utils import timezone
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.core.utils import get_client_ip, get_user_agent
        from .models import UserSession

        token = RefreshToken(refresh_token)
        session_key = str(token.get("jti") or "")[:40] or str(refresh_token)[:40]
        exp = token.get("exp")
        expires_at = (
            timezone.datetime.fromtimestamp(exp, tz=datetime_timezone.utc)
            if exp
            else timezone.now() + timezone.timedelta(days=30)
        )

        UserSession.objects.update_or_create(
            user=user,
            session_key=session_key,
            defaults={
                "ip_address": get_client_ip(request) or "unknown",
                "user_agent": get_user_agent(request) or "",
                "is_active": True,
                "expires_at": expires_at,
            },
        )

        return session_key
    except Exception:
        return None


def deactivate_user_session(user, refresh_token: str | None) -> None:
    """Deactivate a tracked session when logging out."""
    if not refresh_token:
        return

    try:
        from rest_framework_simplejwt.tokens import RefreshToken

        from .models import UserSession

        token = RefreshToken(refresh_token)
        session_key = str(token.get("jti") or "")[:40]
        if session_key:
            UserSession.objects.filter(user=user, session_key=session_key).update(
                is_active=False
            )
    except Exception:
        return


class ProfileValidationService:
    """Service for validating profile data."""

    # Phone number regex patterns
    PHONE_PATTERNS = {
        "ke": r"^\+?254[1-9][0-9]{8}$",  # Kenya
        "generic": r"^\+?[1-9][0-9]{7,14}$",  # Generic international
    }

    @classmethod
    def validate_phone_number(cls, phone_number, country_code="generic"):
        """
        Validate phone number format.

        Args:
            phone_number: Phone number string
            country_code: Country code for specific validation

        Returns:
            tuple: (is_valid, error_message)
        """
        if not phone_number:
            return True, None  # Empty is allowed

        pattern = cls.PHONE_PATTERNS.get(country_code, cls.PHONE_PATTERNS["generic"])

        if not re.match(pattern, phone_number):
            return False, "Invalid phone number format"

        return True, None

    @classmethod
    def validate_year_of_study(cls, year, max_years=6):
        """
        Validate year of study.

        Args:
            year: Year number
            max_years: Maximum years of study

        Returns:
            tuple: (is_valid, error_message)
        """
        if year is None:
            return True, None  # Empty is allowed

        if not isinstance(year, int) or year < 1 or year > max_years:
            return False, f"Year of study must be between 1 and {max_years}"

        return True, None

    @classmethod
    def validate_semester(cls, semester):
        """
        Validate semester.

        Args:
            semester: Semester number

        Returns:
            tuple: (is_valid, error_message)
        """
        if semester is None:
            return True, None  # Empty is allowed

        if not isinstance(semester, int) or semester < 1 or semester > 2:
            return False, "Semester must be 1 or 2"

        return True, None

    @classmethod
    def validate_registration_number(cls, registration_number, user=None):
        """
        Validate registration number uniqueness.

        Args:
            registration_number: Registration number string
            user: Current user instance (for update validation)

        Returns:
            tuple: (is_valid, error_message)
        """
        if not registration_number:
            return True, None  # Empty is allowed

        from .models import User

        # Check uniqueness
        existing = User.objects.filter(registration_number=registration_number)

        if user:
            existing = existing.exclude(pk=user.pk)

        if existing.exists():
            return False, "Registration number already exists"

        return True, None


class ProfileStatsService:
    """Service for getting profile statistics."""

    @classmethod
    def get_user_stats(cls, user):
        """
        Get user activity statistics.

        Args:
            user: User instance

        Returns:
            dict: Statistics dictionary
        """

        profile = getattr(user, "profile", None)

        if not profile:
            return {
                "total_uploads": 0,
                "total_downloads": 0,
                "total_bookmarks": 0,
                "total_comments": 0,
                "total_ratings": 0,
            }

        return {
            "total_uploads": profile.total_uploads,
            "total_downloads": profile.total_downloads,
            "total_bookmarks": profile.total_bookmarks,
            "total_comments": profile.total_comments,
            "total_ratings": profile.total_ratings,
        }

    @classmethod
    def get_storage_summary(cls, user):
        """
        Get storage usage summary.

        Args:
            user: User instance

        Returns:
            dict: Storage summary
        """
        from django.db.models import Sum

        from apps.resources.models import PersonalResource

        aggregation = PersonalResource.objects.filter(user=user).aggregate(
            total_files=Count("id"),
            total_size=Sum("file_size"),
        )
        total_files = int(aggregation.get("total_files") or 0)
        total_size_bytes = int(aggregation.get("total_size") or 0)

        return {
            "total_files": total_files,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        }

    @classmethod
    def get_recent_activity(cls, user, limit=10):
        """
        Get recent user activity.

        Args:
            user: User instance
            limit: Maximum number of activities

        Returns:
            list: Recent activities
        """
        from .models import UserActivity

        activities = UserActivity.objects.filter(user=user).order_by("-created_at")[
            :limit
        ]

        return [
            {
                "action": activity.action,
                "description": activity.description,
                "created_at": activity.created_at,
            }
            for activity in activities
        ]


class PasswordlessAuthService:
    """
    Service wrapper for passwordless authentication.
    Provides unified interface for magic links and passkeys.
    """

    @staticmethod
    def request_magic_link(email: str, ip_address: str = None) -> dict:
        """
        Request a magic link for a user.

        Args:
            email: User's email address
            ip_address: Optional IP address for rate limiting

        Returns:
            dict: Result with success status and message
        """
        from .auth_magic_links import magic_link_service

        result = magic_link_service.request_magic_link(email, ip_address)
        return {
            "success": result.success,
            "message": result.message,
        }

    @staticmethod
    def consume_magic_link(
        token: str,
        ip_address: str = None,
        user_agent: str = "",
    ) -> dict:
        """
        Consume a magic link token and get JWT tokens.

        Args:
            token: The magic link token

        Returns:
            dict: Result with JWT tokens or error
        """
        from .auth_magic_links import magic_link_service

        result = magic_link_service.consume_magic_link(
            token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if result.success:
            return {
                "success": True,
                "message": result.message,
                "access": result.access,
                "refresh": result.refresh,
                "user_id": result.user_id,
            }
        return {
            "success": False,
            "message": result.message,
        }

    @staticmethod
    def get_passkey_registration_options(user, passkey_name: str = None) -> dict:
        """
        Get options for registering a new passkey.

        Args:
            user: The user registering the passkey
            passkey_name: Optional name for the passkey

        Returns:
            dict: Result with registration options
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        result = passkey_service.get_registration_options(user, passkey_name)
        return {
            "success": result.success,
            "message": result.message,
            "options": result.options,
        }

    @staticmethod
    def verify_passkey_registration(user, credential_data: dict, passkey_name: str = None) -> dict:
        """
        Verify passkey registration.

        Args:
            user: The user registering the passkey
            credential_data: The credential data from the client
            passkey_name: Optional name for the passkey

        Returns:
            dict: Result with passkey ID
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        result = passkey_service.verify_registration(user, credential_data, passkey_name)
        return {
            "success": result.success,
            "message": result.message,
            "passkey_id": result.passkey_id,
        }

    @staticmethod
    def get_passkey_authentication_options(user=None) -> dict:
        """
        Get options for passkey authentication.

        Args:
            user: Optional user to get credentials for

        Returns:
            dict: Result with authentication options
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        result = passkey_service.get_authentication_options(user)
        return {
            "success": result.success,
            "message": result.message,
            "options": result.options,
        }

    @staticmethod
    def verify_passkey_authentication(credential_data: dict, expected_user_id: int = None) -> dict:
        """
        Verify passkey authentication.

        Args:
            credential_data: The credential data from the client
            expected_user_id: Optional expected user ID

        Returns:
            dict: Result with user ID and JWT tokens
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        result = passkey_service.verify_authentication(credential_data, expected_user_id)
        if result.success:
            # Generate JWT tokens
            from django.contrib.auth import get_user_model
            from rest_framework_simplejwt.tokens import RefreshToken

            User = get_user_model()
            user = User.objects.get(id=result.user_id)
            refresh = RefreshToken.for_user(user)

            return {
                "success": True,
                "message": result.message,
                "user_id": result.user_id,
                "passkey_id": result.passkey_id,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        return {
            "success": False,
            "message": result.message,
        }

    @staticmethod
    def list_user_passkeys(user) -> list:
        """
        List all passkeys for a user.

        Args:
            user: The user

        Returns:
            list: List of passkey info
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE, PasskeyInfo

        if not FIDO2_AVAILABLE:
            return []

        passkeys = passkey_service.list_passkeys(user)
        return [
            {
                "id": pk.id,
                "name": pk.name,
                "credential_id": pk.credential_id,
                "sign_count": pk.sign_count,
                "backup_eligible": pk.backup_eligible,
                "backup_state": pk.backup_state,
                "created_at": pk.created_at,
                "last_used_at": pk.last_used_at,
            }
            for pk in passkeys
        ]

    @staticmethod
    def delete_user_passkey(user, passkey_id: int) -> dict:
        """
        Delete a passkey for a user.

        Args:
            user: The user
            passkey_id: The passkey ID to delete

        Returns:
            dict: Result with success status
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        success, message = passkey_service.delete_passkey(user, passkey_id)
        return {
            "success": success,
            "message": message,
        }

    @staticmethod
    def update_passkey_name(user, passkey_id: int, new_name: str) -> dict:
        """
        Update a passkey's name.

        Args:
            user: The user
            passkey_id: The passkey ID
            new_name: New name for the passkey

        Returns:
            dict: Result with success status
        """
        from .auth_passkeys import passkey_service, FIDO2_AVAILABLE

        if not FIDO2_AVAILABLE:
            return {
                "success": False,
                "message": "Passkey authentication is not available.",
            }

        success, message = passkey_service.update_passkey_name(user, passkey_id, new_name)
        return {
            "success": success,
            "message": message,
        }
