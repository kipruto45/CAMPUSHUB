"""
Backward-compatible magic-link token helpers.

These wrappers now delegate to the passwordless magic-link service so
older tests and modules use the same token format and TTL behavior.
"""


def generate_magic_link_token(user_id: int, ttl_minutes: int = 15) -> str:
    from .auth_magic_links import MagicLinkToken

    token, _ = MagicLinkToken(ttl_minutes=ttl_minutes).generate(user_id)
    return token


def validate_magic_link_token(token: str) -> dict:
    from .auth_magic_links import MagicLinkToken

    return MagicLinkToken().validate(token)
