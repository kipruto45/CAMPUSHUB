"""Tests for custom mobile throttles."""

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.api.throttles import (MOBILE_THROTTLE_RATES, BurstRateThrottle,
                                DeviceThrottle, IPBasedThrottle,
                                MobileAnonRateThrottle, MobileAuthRateThrottle,
                                MobileAuthenticateThrottle,
                                MobileDownloadThrottle, MobileUploadThrottle,
                                MobileUserRateThrottle, SustainedRateThrottle,
                                get_client_ip)


def _request(method, path, user=None, data=None, **extra):
    factory = APIRequestFactory()
    payload = data or {}
    request = getattr(factory, method.lower())(path, data=payload, **extra)
    request.user = user if user is not None else AnonymousUser()
    request.data = payload
    return request


def _view(action=None):
    return type("ViewStub", (), {"action": action})()


def test_mobile_user_rate_throttle_cache_key_for_authenticated_and_anonymous(user):
    throttle = MobileUserRateThrottle()
    auth_request = _request("GET", "/api/mobile/home/", user=user)
    anon_request = _request("GET", "/api/mobile/home/")
    anon_request.META["REMOTE_ADDR"] = "127.0.0.11"

    auth_key = throttle.get_cache_key(auth_request, _view())
    anon_key = throttle.get_cache_key(anon_request, _view())

    assert str(user.pk) in auth_key
    assert "127.0.0.11" in anon_key


def test_mobile_anon_rate_throttle_skips_safe_methods_and_throttles_mutations():
    throttle = MobileAnonRateThrottle()
    get_request = _request("GET", "/api/mobile/resources/")
    post_request = _request("POST", "/api/mobile/resources/")
    post_request.META["REMOTE_ADDR"] = "127.0.0.12"

    assert throttle.get_cache_key(get_request, _view()) is None
    key = throttle.get_cache_key(post_request, _view())
    assert key is not None
    assert "127.0.0.12" in key


def test_mobile_auth_rate_throttle_uses_user_id_with_ip_fallback(user):
    throttle = MobileAuthRateThrottle()
    auth_request = _request("POST", "/api/mobile/resources/", user=user)
    anon_request = _request("POST", "/api/mobile/resources/")
    anon_request.META["REMOTE_ADDR"] = "127.0.0.13"

    auth_key = throttle.get_cache_key(auth_request, _view())
    anon_key = throttle.get_cache_key(anon_request, _view())

    assert str(user.pk) in auth_key
    assert "127.0.0.13" in anon_key


def test_mobile_upload_throttle_actions_and_path_detection(user):
    throttle = MobileUploadThrottle()
    post_upload = _request("POST", "/api/mobile/upload/", user=user)
    post_non_upload = _request("POST", "/api/mobile/resources/", user=user)

    assert throttle.get_cache_key(post_upload, _view(action="create")) is not None
    assert throttle.get_cache_key(post_upload, _view(action="list")) is None
    assert throttle.get_cache_key(post_non_upload, _view()) is None
    assert throttle.get_cache_key(post_upload, _view()) is not None


def test_mobile_download_throttle_actions_and_path_detection(user):
    throttle = MobileDownloadThrottle()
    get_download = _request("GET", "/api/mobile/resources/download/", user=user)
    post_download = _request("POST", "/api/mobile/resources/download/", user=user)
    patch_download = _request("PATCH", "/api/mobile/resources/download/", user=user)

    assert throttle.get_cache_key(get_download, _view(action="download")) is not None
    assert throttle.get_cache_key(get_download, _view(action="list")) is None
    assert throttle.get_cache_key(post_download, _view()) is not None
    assert throttle.get_cache_key(patch_download, _view()) is None


def test_mobile_authenticate_throttle_action_based_ident_selection(user):
    throttle = MobileAuthenticateThrottle()
    login_request = _request(
        "POST",
        "/api/mobile/login/",
        user=user,
        data={"email": "student@test.com"},
        format="json",
    )
    other_action_request = _request(
        "POST",
        "/api/mobile/profile/",
        user=user,
        data={},
        format="json",
    )

    key = throttle.get_cache_key(login_request, _view(action="login"))
    assert "student@test.com" in key
    assert throttle.get_cache_key(other_action_request, _view(action="list")) is None


def test_mobile_authenticate_throttle_url_name_and_path_fallbacks():
    throttle = MobileAuthenticateThrottle()

    by_url_name = _request(
        "POST",
        "/any-path/",
        data={"registration_number": "REG001"},
        format="json",
    )
    by_url_name.resolver_match = type("Resolver", (), {"url_name": "mobile_register"})()
    key_url_name = throttle.get_cache_key(by_url_name, _view())
    assert "REG001" in key_url_name

    disallowed_url_name = _request("POST", "/any-path/", data={}, format="json")
    disallowed_url_name.resolver_match = type("Resolver", (), {"url_name": "health"})()
    assert throttle.get_cache_key(disallowed_url_name, _view()) is None

    by_path = _request("POST", "/api/mobile/refresh/", data={}, format="json")
    by_path.META["REMOTE_ADDR"] = "127.0.0.14"
    by_path.resolver_match = None
    key_path = throttle.get_cache_key(by_path, _view())
    assert "127.0.0.14" in key_path

    disallowed_path = _request("POST", "/api/mobile/profile/", data={}, format="json")
    disallowed_path.resolver_match = None
    assert throttle.get_cache_key(disallowed_path, _view()) is None


def test_rate_constant_defaults_and_simple_scopes():
    assert MOBILE_THROTTLE_RATES["mobile_anon"] == "30/minute"
    assert MOBILE_THROTTLE_RATES["mobile_auth"] == "200/hour"
    assert BurstRateThrottle.scope == "burst"
    assert SustainedRateThrottle.scope == "sustained"


def test_get_client_ip_prefers_forwarded_header_then_remote_addr():
    forwarded = _request("GET", "/api/mobile/home/")
    forwarded.META["HTTP_X_FORWARDED_FOR"] = "196.1.2.3, 10.0.0.1"
    forwarded.META["REMOTE_ADDR"] = "127.0.0.1"
    assert get_client_ip(forwarded) == "196.1.2.3"

    remote_only = _request("GET", "/api/mobile/home/")
    remote_only.META["REMOTE_ADDR"] = "127.0.0.22"
    assert get_client_ip(remote_only) == "127.0.0.22"


def test_ip_based_throttle_uses_client_ip():
    throttle = IPBasedThrottle()
    request = _request("GET", "/api/mobile/home/")
    request.META["REMOTE_ADDR"] = "127.0.0.23"

    key = throttle.get_cache_key(request, _view())
    assert "127.0.0.23" in key


def test_device_throttle_uses_device_token_and_returns_none_without_it():
    throttle = DeviceThrottle()
    with_token = _request("GET", "/api/mobile/home/", HTTP_X_DEVICE_TOKEN="abc123token")
    without_token = _request("GET", "/api/mobile/home/")

    assert "abc123token" in throttle.get_cache_key(with_token, _view())
    assert throttle.get_cache_key(without_token, _view()) is None
