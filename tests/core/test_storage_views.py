import hashlib
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.core.storage import FileCategory, get_storage_service
from apps.core.storage import service as storage_service_module
from apps.core.storage.views import (
    complete_upload,
    get_signed_url,
    initiate_upload,
    serve_public_file,
)
from apps.resources.models import UserStorage

User = get_user_model()


@pytest.fixture
def storage_test_env(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.MEDIA_URL = "/media/"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "storage-view-tests",
        }
    }
    settings.CLOUDINARY_CLOUD_NAME = ""

    cache.clear()
    storage_service_module._storage_service = None
    storage_service_module.StorageService._instance = None

    yield Path(settings.MEDIA_ROOT)

    cache.clear()
    storage_service_module._storage_service = None
    storage_service_module.StorageService._instance = None


@pytest.mark.django_db
def test_get_signed_url_allows_post_for_owner(storage_test_env, user):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile("private.pdf", b"private-content", content_type="application/pdf")
    saved = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )
    factory = APIRequestFactory()
    request = factory.post(
        "/api/storage/sign/",
        {"path": saved.path, "expires": 600, "download": True},
        format="json",
    )
    force_authenticate(request, user=user)

    response = get_signed_url(request)

    assert response.status_code == 200
    assert response.data["path"] == saved.path
    assert response.data["expires_in"] == 600
    assert response.data["download"] is True


@pytest.mark.django_db
def test_get_signed_url_denies_non_owner(storage_test_env, user):
    storage = get_storage_service()
    other_user = User.objects.create_user(
        email="other-student@test.com",
        password="testpass123",
        full_name="Other Student",
        registration_number="STU999",
        role="student",
    )
    uploaded_file = SimpleUploadedFile("private.pdf", b"private-content", content_type="application/pdf")
    saved = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )
    factory = APIRequestFactory()
    request = factory.post(
        "/api/storage/sign/",
        {"path": saved.path},
        format="json",
    )
    force_authenticate(request, user=other_user)

    response = get_signed_url(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_complete_upload_is_idempotent(storage_test_env, authenticated_client, user):
    factory = APIRequestFactory()
    init_request = factory.post(
        "/api/storage/upload/init/",
        {
            "filename": "notes.txt",
            "file_size": 4,
            "content_type": "text/plain",
            "category": "personal",
        },
        format="json",
    )
    force_authenticate(init_request, user=user)

    init_response = initiate_upload(init_request)
    assert init_response.status_code == 200

    upload_id = init_response.data["upload_id"]
    path = init_response.data["path"]

    storage = get_storage_service()
    full_path = storage._backend._full_path(path)
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)
    Path(full_path).write_bytes(b"test")
    checksum = hashlib.md5(b"test").hexdigest()

    complete_request = factory.post(
        "/api/storage/upload/complete/",
        {"upload_id": upload_id, "path": path, "checksum": checksum},
        format="json",
    )
    force_authenticate(complete_request, user=user)
    complete_response = complete_upload(complete_request)

    assert complete_response.status_code == 200
    assert complete_response.data["success"] is True

    second_request = factory.post(
        "/api/storage/upload/complete/",
        {"upload_id": upload_id, "path": path, "checksum": checksum},
        format="json",
    )
    force_authenticate(second_request, user=user)
    second_response = complete_upload(second_request)

    storage_record = UserStorage.objects.get(user=user)
    assert second_response.status_code == 200
    assert second_response.data["already_completed"] is True
    assert storage_record.used_storage == 4


@pytest.mark.django_db
def test_serve_public_file_rejects_private_resource(storage_test_env, user):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile("private.pdf", b"private-content", content_type="application/pdf")
    saved = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )
    factory = APIRequestFactory()
    request = factory.get(f"/api/storage/public/{saved.path}/")

    response = serve_public_file(request, saved.path)

    assert response.status_code == 403

