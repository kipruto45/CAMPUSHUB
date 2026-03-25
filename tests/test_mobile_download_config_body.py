import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from apps.api.mobile_views import mobile_download_config


@pytest.mark.django_db
def test_download_config_body(settings):
    settings.DOWNLOAD_DIRECTORY = "CampusHub/Downloads"
    settings.DOWNLOAD_TO_APP_DIRECTORY = True
    settings.PREVENT_SYSTEM_DOWNLOADS = True

    factory = APIRequestFactory()
    User = get_user_model()
    user = User.objects.create_user(username="cfguser", email="c@ex.com", password="pass")

    request = factory.get("/api/v1/mobile/download-config/")
    force_authenticate(request, user=user)
    resp = mobile_download_config(request)

    assert resp.status_code == 200
    cfg = resp.data["download_config"]
    assert cfg["download_directory"] == "CampusHub/Downloads"
    assert cfg["download_to_app_directory"] is True
    assert cfg["prevent_system_downloads"] is True
