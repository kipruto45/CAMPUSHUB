import hashlib
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.storage import FileAccessControl, FileCategory, FileVisibility, get_storage_service
from apps.core.storage import service as storage_service_module


@pytest.fixture
def storage_test_env(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.MEDIA_URL = "/media/"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "storage-tests",
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
def test_save_private_persists_round_trip_metadata(storage_test_env, user):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "lecture-notes.pdf",
        b"hello storage",
        content_type="application/pdf",
    )

    result = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )

    assert result.success is True
    metadata = storage.get_metadata(result.path)
    assert metadata.visibility == FileVisibility.PRIVATE
    assert metadata.category == FileCategory.PERSONAL
    assert metadata.uploaded_by == user.id
    assert metadata.content_type == "application/pdf"
    assert metadata.checksum == hashlib.md5(b"hello storage").hexdigest()
    assert FileAccessControl.can_access(user, metadata) is True


@pytest.mark.django_db
def test_get_metadata_infers_private_owner_without_sidecar(storage_test_env, user):
    storage = get_storage_service()
    path = f"personal/{user.id}/2026/03/manual.txt"
    full_path = storage._backend._full_path(path)
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)
    Path(full_path).write_bytes(b"inferred metadata")

    metadata = storage.get_metadata(path)

    assert metadata.visibility == FileVisibility.PRIVATE
    assert metadata.category == FileCategory.PERSONAL
    assert metadata.uploaded_by == user.id
    assert metadata.content_type == "text/plain"


@pytest.mark.django_db
def test_storage_service_rejects_path_traversal(storage_test_env):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile("escape.txt", b"blocked")

    result = storage.save(uploaded_file, "../escape.txt")

    assert result.success is False
    assert "Unsafe storage path" in result.error
    assert storage.exists("../escape.txt") is False

