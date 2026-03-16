"""Tests for health and readiness endpoints."""

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from apps.core import health


@pytest.mark.django_db
def test_health_endpoint_returns_healthy(api_client):
    response = api_client.get("/health/")

    assert response.status_code == 200
    assert response.data["status"] == "healthy"
    assert response.data["database"] == "healthy"
    assert response.data["cache"] == "healthy"


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "health-ready-test",
        }
    },
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    },
)
@pytest.mark.django_db
def test_readiness_endpoint_returns_ready(api_client):
    factory = APIRequestFactory()
    response = health.readiness_check(factory.get("/health/ready/"))

    assert response.status_code == 200
    assert response.data["status"] == "ready"
    assert response.data["database"] == "healthy"
    assert response.data["cache"] == "healthy"
    assert response.data["channel_layer"].startswith("healthy:")


def test_health_check_returns_503_when_database_fails(monkeypatch):
    factory = APIRequestFactory()

    def failing_cursor():
        raise RuntimeError("db offline")

    monkeypatch.setattr(health.connection, "cursor", failing_cursor)
    response = health.health_check(factory.get("/health/"))

    assert response.status_code == 503
    assert response.data["status"] == "unhealthy"
    assert "unhealthy: db offline" in response.data["database"]


def test_health_check_returns_503_when_cache_raises(monkeypatch):
    factory = APIRequestFactory()

    def failing_set(*args, **kwargs):
        raise RuntimeError("cache offline")

    monkeypatch.setattr(health.cache, "set", failing_set)
    response = health.health_check(factory.get("/health/"))

    assert response.status_code == 503
    assert response.data["status"] == "unhealthy"
    assert "unhealthy: cache offline" in response.data["cache"]


def test_health_check_returns_503_when_cache_roundtrip_fails(monkeypatch):
    factory = APIRequestFactory()

    monkeypatch.setattr(health.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(health.cache, "get", lambda *args, **kwargs: "bad")
    response = health.health_check(factory.get("/health/"))

    assert response.status_code == 503
    assert response.data["status"] == "unhealthy"
    assert response.data["cache"] == "unhealthy: cache not working"


def test_readiness_check_returns_503_when_database_fails(monkeypatch):
    factory = APIRequestFactory()

    def failing_cursor():
        raise RuntimeError("db offline")

    monkeypatch.setattr(health.connection, "cursor", failing_cursor)
    response = health.readiness_check(factory.get("/health/ready/"))

    assert response.status_code == 503
    assert response.data["status"] == "not_ready"
    assert "unhealthy: db offline" in response.data["database"]


def test_readiness_check_returns_503_when_channel_layer_missing(settings):
    factory = APIRequestFactory()
    settings.CHANNEL_LAYERS = {}

    response = health.readiness_check(factory.get("/health/ready/"))

    assert response.status_code == 503
    assert response.data["status"] == "not_ready"
    assert response.data["channel_layer"] == "unhealthy: channel layer backend missing"
