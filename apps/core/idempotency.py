"""Helpers for idempotent write operations (safe retries)."""

from __future__ import annotations

import hashlib
from typing import Any

from django.core.cache import cache
from rest_framework.response import Response

IDEMPOTENCY_HEADER = "HTTP_X_IDEMPOTENCY_KEY"
DEFAULT_IDEMPOTENCY_TTL_SECONDS = 300


def _build_cache_key(request) -> str | None:
    """Build a stable idempotency cache key from request context."""
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    idempotency_key = (request.META.get(IDEMPOTENCY_HEADER) or "").strip()
    if not idempotency_key:
        return None

    user_part = "anon"
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        user_part = str(user.pk)

    body = getattr(request, "body", b"") or b""
    payload_hash = hashlib.sha256(body).hexdigest()

    return (
        f"idempotency:{user_part}:{request.method.upper()}:"
        f"{request.path}:{idempotency_key}:{payload_hash}"
    )


def get_cached_idempotent_response(request) -> Response | None:
    """Return cached response for repeated idempotency key (if any)."""
    cache_key = _build_cache_key(request)
    if not cache_key:
        return None

    cached = cache.get(cache_key)
    if not cached:
        return None

    response = Response(cached.get("data"), status=cached.get("status", 200))
    for header_name, header_value in (cached.get("headers") or {}).items():
        response[header_name] = header_value
    response["X-Idempotent-Replay"] = "true"
    return response


def cache_idempotent_response(
    request, response: Response, ttl_seconds: int = DEFAULT_IDEMPOTENCY_TTL_SECONDS
) -> Response:
    """
    Cache successful write responses so client retries return same result.

    Only 2xx responses are cached. Errors are not cached to keep recovery behavior
    straightforward for clients.
    """
    cache_key = _build_cache_key(request)
    if not cache_key:
        return response

    if 200 <= int(getattr(response, "status_code", 0)) < 300:
        data: Any = getattr(response, "data", None)
        if data is None and response.status_code == 204:
            data = {}
        cache.set(
            cache_key,
            {
                "status": response.status_code,
                "data": data,
                "headers": {},
            },
            ttl_seconds,
        )
        response["X-Idempotent-Replay"] = "false"

    return response
