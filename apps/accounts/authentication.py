"""
Custom authentication for CampusHub using JWT.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import (AuthenticationFailed,
                                                 InvalidToken)

from .models import User


class JWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that handles user lookup.
    """

    def get_user(self, validated_token):
        """Get user from validated token."""
        try:
            user_id = validated_token.get("user_id")
            if user_id is None:
                raise InvalidToken(
                    "Token contained no recognizable user identification."
                )

            user = User.objects.get(id=user_id)

            if not user.is_active:
                raise AuthenticationFailed("User account is disabled.")

            return user

        except (InvalidToken, AuthenticationFailed):
            raise
        except User.DoesNotExist:
            raise InvalidToken("User not found.")

        except Exception as e:
            raise InvalidToken(str(e))

    def authenticate(self, request):
        """Authenticate the request and return a tuple of (user, token)."""
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return (self.get_user(validated_token), validated_token)

        except Exception:
            return None


def generate_tokens_for_user(user, remember_me=False):
    """
    Generate access and refresh tokens for a user.

    Args:
        user: The user to generate tokens for
        remember_me: If True, sets a longer refresh token lifetime (90 days)
                    If False, uses default lifetime (30 days as per settings)
    """
    from datetime import timedelta

    from rest_framework_simplejwt.tokens import RefreshToken

    # Create refresh token
    refresh = RefreshToken.for_user(user)

    # If remember_me is True, extend the refresh token lifetime to 90 days
    if remember_me:
        refresh.set_exp(lifetime=timedelta(days=90))

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
