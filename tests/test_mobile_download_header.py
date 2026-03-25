import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from apps.api.mobile_views import mobile_download_resource
from apps.resources.models import Resource
from decimal import Decimal


@pytest.mark.django_db
def test_download_response_has_directory_header(settings):
    settings.DOWNLOAD_DIRECTORY = "CampusHub/Downloads"
    settings.PREVENT_SYSTEM_DOWNLOADS = True
    factory = APIRequestFactory()
    User = get_user_model()
    user = User.objects.create_user(username="duser", email="d@ex.com", password="pass")
    resource = Resource.objects.create(
        title="File",
        uploaded_by=user,
        status="approved",
        is_public=True,
        file_type="pdf",
        file_size=0,
    )

    request = factory.get(f"/api/v1/mobile/resources/{resource.id}/download/")
    force_authenticate(request, user=user)
    resp = mobile_download_resource(request, resource_id=resource.id)

    assert resp.status_code in (200, 201, 202)
    assert resp["X-Download-Directory"] == "CampusHub/Downloads"
    assert resp["X-Prevent-System-Downloads"] == "true"
