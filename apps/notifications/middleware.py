"""Custom middleware for JWT-authenticated WebSocket connections."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


class JWTAuthMiddleware(BaseMiddleware):
    """Resolve `scope['user']` from JWT token in query params or Authorization header."""

    async def __call__(self, scope, receive, send):
        user = scope.get("user")
        if user and getattr(user, "is_authenticated", False):
            return await super().__call__(scope, receive, send)

        scope["user"] = AnonymousUser()
        token = self._extract_token(scope)

        if token:
            resolved_user = await self._resolve_user(token)
            if resolved_user is not None:
                scope["user"] = resolved_user

        return await super().__call__(scope, receive, send)

    @staticmethod
    def _extract_token(scope) -> str | None:
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)

        for key in ("token", "access", "jwt"):
            values = params.get(key)
            if values and values[0]:
                return values[0]

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization")
        if not auth_header:
            return None

        value = auth_header.decode("utf-8")
        if value.lower().startswith("bearer "):
            return value.split(" ", 1)[1].strip()
        return value.strip() or None

    async def _resolve_user(self, token: str):
        try:
            payload = AccessToken(token)
            user_id = payload.get("user_id")
            if user_id is None:
                return None
            return await self._get_user_by_id(user_id)
        except (TokenError, Exception):
            return None

    @database_sync_to_async
    def _get_user_by_id(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None
