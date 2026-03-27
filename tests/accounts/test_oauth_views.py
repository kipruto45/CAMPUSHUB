"""Tests for OAuth API endpoints."""

from urllib.parse import parse_qs, urlparse

import pytest


class MockResponse:
    def __init__(
        self,
        status_code=200,
        payload=None,
        content=b"",
        headers=None,
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload


@pytest.mark.django_db
def test_google_oauth_requires_authorization_code(api_client):
    response = api_client.post("/api/auth/google/", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "Authorization code is required"


@pytest.mark.django_db
def test_google_oauth_returns_400_on_token_exchange_failure(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views

    monkeypatch.setattr(
        oauth_views,
        "get_google_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(status_code=400),
    )

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"] == "Failed to exchange code for tokens"


@pytest.mark.django_db
def test_google_oauth_returns_400_on_userinfo_failure(api_client, monkeypatch):
    from apps.accounts import oauth_views

    monkeypatch.setattr(
        oauth_views,
        "get_google_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "get",
        lambda *args, **kwargs: MockResponse(status_code=400),
    )

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"] == "Failed to get user info"


@pytest.mark.django_db
def test_google_oauth_success_returns_user_and_tokens(
    api_client,
    user,
    monkeypatch,
):
    from apps.accounts import oauth_views

    captured = {}

    monkeypatch.setattr(
        oauth_views,
        "get_google_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "get",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"email": user.email, "name": user.full_name},
        ),
    )

    def fake_process_google_user(data):
        captured["data"] = data
        return user

    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "process_google_user",
        fake_process_google_user,
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "generate_tokens_for_social_user",
        lambda user_obj: {
            "access": "access-token",
            "refresh": "refresh-token",
        },
    )

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["message"] == "Google authentication successful"
    assert response.data["access"] == "access-token"
    assert response.data["refresh"] == "refresh-token"
    assert response.data["access_token"] == "access-token"
    assert response.data["refresh_token"] == "refresh-token"
    assert response.data["tokens"]["access"] == "access-token"
    assert captured["data"]["email"] == user.email


@pytest.mark.django_db
def test_google_oauth_sends_welcome_email_for_new_social_user(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views
    from apps.accounts.models import User

    new_email = "new-google-social@test.com"
    captured = {"calls": 0}

    monkeypatch.setattr(
        oauth_views,
        "get_google_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "get",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"email": new_email, "name": "New Google User"},
        ),
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "process_google_user",
        lambda data: User.objects.create_user(
            email=data["email"],
            password=None,
            full_name=data.get("name", ""),
            is_verified=True,
            auth_provider="google",
        ),
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "generate_tokens_for_social_user",
        lambda user_obj: {"access": "a", "refresh": "r"},
    )
    monkeypatch.setattr(
        oauth_views,
        "_send_social_welcome_email",
        lambda request, user, provider: captured.__setitem__(
            "calls",
            captured["calls"] + 1,
        ),
    )

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 200
    assert captured["calls"] == 1


@pytest.mark.django_db
def test_google_oauth_returns_500_on_unhandled_exception(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(oauth_views, "get_google_provider_config", boom)

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 500
    assert (
        response.data["error"]
        == "We couldn't sign you in with Google right now. Please try again."
    )


def test_google_oauth_url_endpoint_returns_authorization_url(api_client):
    response = api_client.get("/api/auth/google/url/")

    assert response.status_code == 200
    url = response.data["authorization_url"]
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert "client_id" in params
    assert params["response_type"] == ["code"]


@pytest.mark.django_db
def test_google_oauth_uses_mobile_redirect_uri_for_token_exchange(
    api_client,
    user,
    monkeypatch,
):
    from apps.accounts import oauth_views

    captured_redirect = {}

    monkeypatch.setattr(
        oauth_views,
        "get_google_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )

    def fake_post(*args, **kwargs):
        captured_redirect["value"] = kwargs["data"]["redirect_uri"]
        return MockResponse(status_code=200, payload={"access_token": "token-1"})

    monkeypatch.setattr(oauth_views.requests, "post", fake_post)
    monkeypatch.setattr(
        oauth_views.requests,
        "get",
        lambda *args, **kwargs: MockResponse(
            status_code=200, payload={"email": user.email, "name": user.full_name}
        ),
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "process_google_user",
        lambda data: user,
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "generate_tokens_for_social_user",
        lambda user_obj: {"access": "a", "refresh": "r"},
    )

    response = api_client.post(
        "/api/auth/google/",
        {"code": "abc", "redirect_uri": "campushub://callback/google"},
        format="json",
    )

    assert response.status_code == 200
    assert captured_redirect["value"] == "campushub://callback/google"


def test_google_oauth_url_endpoint_applies_mobile_redirect_override(api_client):
    response = api_client.get(
        "/api/auth/google/url/?redirect_uri=campushub://callback/google"
    )

    assert response.status_code == 200
    url = response.data["authorization_url"]
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert params["redirect_uri"] == ["campushub://callback/google"]


def test_google_oauth_url_endpoint_ignores_unsafe_redirect_override(api_client):
    response = api_client.get(
        "/api/auth/google/url/?redirect_uri=https://evil.example/callback"
    )

    assert response.status_code == 200
    url = response.data["authorization_url"]
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert params["redirect_uri"] != ["https://evil.example/callback"]


def test_google_oauth_callback_bridges_to_mobile_deeplink(api_client):
    response = api_client.get(
        "/api/auth/google/callback/?code=test-code-123&state=opaque-state",
        follow=False,
    )

    assert response.status_code == 302
    assert response["Location"].startswith("campushub://callback/google")
    parsed = urlparse(response["Location"])
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert params["code"] == ["test-code-123"]
    assert params["state"] == ["opaque-state"]


@pytest.mark.django_db
def test_microsoft_oauth_requires_authorization_code(api_client):
    response = api_client.post("/api/auth/microsoft/", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "Authorization code is required"


@pytest.mark.django_db
def test_microsoft_oauth_returns_400_on_token_exchange_failure(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views

    monkeypatch.setattr(
        oauth_views,
        "get_microsoft_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(status_code=401),
    )

    response = api_client.post(
        "/api/auth/microsoft/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"] == "Failed to exchange code for tokens"


@pytest.mark.django_db
def test_microsoft_oauth_returns_400_on_userinfo_failure(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views

    monkeypatch.setattr(
        oauth_views,
        "get_microsoft_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "get",
        lambda *args, **kwargs: MockResponse(status_code=400),
    )

    response = api_client.post(
        "/api/auth/microsoft/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"] == "Failed to get user info"


@pytest.mark.django_db
def test_microsoft_oauth_success_with_photo_bytes(
    api_client,
    user,
    monkeypatch,
):
    from apps.accounts import oauth_views

    captured = {}
    calls = {"get": 0}

    monkeypatch.setattr(
        oauth_views,
        "get_microsoft_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )

    def fake_get(*args, **kwargs):
        calls["get"] += 1
        if calls["get"] == 1:
            return MockResponse(
                status_code=200,
                payload={
                    "mail": user.email,
                    "displayName": "Test User",
                    "id": "ms-1",
                },
            )
        return MockResponse(
            status_code=200,
            content=b"img",
            headers={"Content-Type": "image/png"},
        )

    monkeypatch.setattr(oauth_views.requests, "get", fake_get)

    def fake_process_microsoft_user(data):
        captured["data"] = data
        return user

    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "process_microsoft_user",
        fake_process_microsoft_user,
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "generate_tokens_for_social_user",
        lambda user_obj: {
            "access": "access-token",
            "refresh": "refresh-token",
        },
    )

    response = api_client.post(
        "/api/auth/microsoft/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["message"] == "Microsoft authentication successful"
    assert response.data["access"] == "access-token"
    assert response.data["refresh"] == "refresh-token"
    assert response.data["access_token"] == "access-token"
    assert response.data["refresh_token"] == "refresh-token"
    assert response.data["tokens"]["refresh"] == "refresh-token"
    assert captured["data"]["photo_content"] == b"img"
    assert captured["data"]["photo_content_type"] == "image/png"


@pytest.mark.django_db
def test_microsoft_oauth_sends_welcome_email_for_new_social_user(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views
    from apps.accounts.models import User

    new_email = "new-microsoft-social@test.com"
    captured = {"calls": 0, "get_calls": 0}

    monkeypatch.setattr(
        oauth_views,
        "get_microsoft_provider_config",
        lambda: {
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "http://localhost/callback",
            "token_url": "https://token.example",
            "userinfo_url": "https://userinfo.example",
            "scope": "openid",
            "auth_url": "https://auth.example",
        },
    )
    monkeypatch.setattr(
        oauth_views.requests,
        "post",
        lambda *args, **kwargs: MockResponse(
            status_code=200,
            payload={"access_token": "token-1"},
        ),
    )

    def fake_get(*args, **kwargs):
        captured["get_calls"] += 1
        if captured["get_calls"] == 1:
            return MockResponse(
                status_code=200,
                payload={
                    "mail": new_email,
                    "displayName": "New Microsoft User",
                    "id": "ms-1",
                },
            )
        return MockResponse(status_code=404)

    monkeypatch.setattr(oauth_views.requests, "get", fake_get)
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "process_microsoft_user",
        lambda data: User.objects.create_user(
            email=data["mail"],
            password=None,
            full_name=data.get("displayName", ""),
            is_verified=True,
            auth_provider="microsoft",
        ),
    )
    monkeypatch.setattr(
        oauth_views.SocialAuthService,
        "generate_tokens_for_social_user",
        lambda user_obj: {"access": "a", "refresh": "r"},
    )
    monkeypatch.setattr(
        oauth_views,
        "_send_social_welcome_email",
        lambda request, user, provider: captured.__setitem__(
            "calls",
            captured["calls"] + 1,
        ),
    )

    response = api_client.post(
        "/api/auth/microsoft/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 200
    assert captured["calls"] == 1


@pytest.mark.django_db
def test_microsoft_oauth_returns_500_on_unhandled_exception(
    api_client,
    monkeypatch,
):
    from apps.accounts import oauth_views

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(oauth_views, "get_microsoft_provider_config", boom)

    response = api_client.post(
        "/api/auth/microsoft/",
        {"code": "abc"},
        format="json",
    )

    assert response.status_code == 500
    assert (
        response.data["error"]
        == "We couldn't sign you in with Microsoft right now. Please try again."
    )


@pytest.mark.django_db
def test_google_oauth_link_hides_internal_errors(
    api_client,
    user,
    monkeypatch,
):
    from apps.accounts import oauth_views
    from apps.accounts.services import LinkedAccountService

    api_client.force_authenticate(user=user)
    monkeypatch.setattr(
        oauth_views,
        "_fetch_google_userinfo_from_access_token",
        lambda access_token: {
            "id": "google-user-123",
            "email": "linked@example.com",
        },
    )

    def boom(*args, **kwargs):
        raise RuntimeError("database timeout")

    monkeypatch.setattr(LinkedAccountService, "link_account", boom)

    response = api_client.post(
        "/api/auth/google/link/",
        {"access_token": "token"},
        format="json",
    )

    assert response.status_code == 500
    assert (
        response.data["detail"]
        == "We couldn't link your Google account right now. Please try again."
    )


def test_microsoft_oauth_url_endpoint_returns_authorization_url(api_client):
    response = api_client.get("/api/auth/microsoft/url/")

    assert response.status_code == 200
    url = response.data["authorization_url"]
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert "client_id" in params
    assert params["response_type"] == ["code"]


def test_microsoft_oauth_callback_bridges_to_mobile_deeplink(api_client):
    response = api_client.get(
        (
            "/api/auth/microsoft/callback/"
            "?error=access_denied&error_description=cancelled&state=opaque-state"
        ),
        follow=False,
    )

    assert response.status_code == 302
    assert response["Location"].startswith("campushub://callback/microsoft")
    parsed = urlparse(response["Location"])
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert params["error"] == ["access_denied"]
    assert params["state"] == ["opaque-state"]
