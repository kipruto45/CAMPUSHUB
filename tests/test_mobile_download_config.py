import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model
from django.conf import settings

from apps.api.mobile_views import mobile_download_config


@pytest.mark.django_db
def test_mobile_download_config_returns_settings():
    factory = APIRequestFactory()
    user = get_user_model().objects.create_user(
        username="dluser", email="dl@example.com", password="pass1234"
    )

    request = factory.get("/api/v1/mobile/download-config/")
    force_authenticate(request, user=user)

    response = mobile_download_config(request)

    assert response.status_code == 200
    cfg = response.data["download_config"]
    assert cfg["download_directory"] == getattr(settings, "DOWNLOAD_DIRECTORY", "CampusHub/Downloads")
    assert cfg["download_to_app_directory"] == getattr(settings, "DOWNLOAD_TO_APP_DIRECTORY", True)
    assert cfg["prevent_system_downloads"] == getattr(settings, "PREVENT_SYSTEM_DOWNLOADS", True)
