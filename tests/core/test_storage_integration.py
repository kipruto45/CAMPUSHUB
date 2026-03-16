import hashlib
import sys
import types
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.activity.models import ActivityType, RecentActivity
from apps.core.storage import (
    CloudinaryStorageBackend,
    FileCategory,
    FileMetadata,
    FileVisibility,
    get_storage_service,
)
from apps.core.storage import service as storage_service_module
from apps.core.storage import views as storage_views
from apps.downloads.models import Download
from apps.resources.models import UserStorage


@pytest.fixture
def storage_test_env(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.MEDIA_URL = "/media/"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "storage-integration-tests",
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
def test_storage_sign_endpoint_is_routed_and_accessible(storage_test_env, authenticated_client, user):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "notes.pdf",
        b"private notes",
        content_type="application/pdf",
    )
    saved = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )

    response = authenticated_client.post(
        "/api/storage/sign/",
        {"path": saved.path, "expires": 900},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["path"] == saved.path
    assert response.json()["expires_in"] == 900


@pytest.mark.django_db
def test_storage_sign_endpoint_uses_model_backed_personal_file_access(storage_test_env, authenticated_client, user):
    from apps.resources.models import PersonalResource

    personal_file = PersonalResource.objects.create(
        user=user,
        title="Model Backed Personal File",
        file=SimpleUploadedFile("model-backed.txt", b"personal-body"),
    )

    response = authenticated_client.post(
        "/api/storage/sign/",
        {"path": personal_file.file.name, "expires": 300},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["path"] == personal_file.file.name
    assert response.json()["expires_in"] == 300


@pytest.mark.django_db
def test_public_file_route_streams_local_file(storage_test_env, api_client):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "public-notes.txt",
        b"public notes",
        content_type="text/plain",
    )
    saved = storage.save_public(uploaded_file, resource_id=99, filename=uploaded_file.name)

    response = api_client.get(f"/api/storage/public/{saved.path}/")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert b"".join(response.streaming_content) == b"public notes"


@pytest.mark.django_db
def test_public_resource_download_route_records_metrics_once(storage_test_env, authenticated_client, user, admin_user):
    from apps.resources.models import Resource

    resource = Resource.objects.create(
        title="Storage Public Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
        file=SimpleUploadedFile("storage-resource.pdf", b"resource-content"),
    )

    first_response = authenticated_client.get(
        f"/api/storage/public/{resource.file.name}/?download=1",
    )
    repeat_response = authenticated_client.get(
        f"/api/storage/public/{resource.file.name}/?download=1",
    )

    resource.refresh_from_db()
    assert first_response.status_code == 200
    assert repeat_response.status_code == 200
    assert resource.download_count == 1
    assert Download.objects.filter(user=user, resource=resource).count() == 1
    assert RecentActivity.objects.filter(
        user=user,
        resource=resource,
        activity_type=ActivityType.DOWNLOADED_RESOURCE,
    ).count() == 1


@pytest.mark.django_db
def test_public_file_route_supports_head_requests(storage_test_env, api_client):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "public-head.txt",
        b"head-check",
        content_type="text/plain",
    )
    saved = storage.save_public(uploaded_file, resource_id=100, filename=uploaded_file.name)

    response = api_client.head(f"/api/storage/public/{saved.path}/")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert response["Content-Length"] == str(len(b"head-check"))
    assert response["Accept-Ranges"] == "bytes"
    assert response.content == b""


@pytest.mark.django_db
def test_public_file_route_returns_304_for_matching_etag(storage_test_env, api_client):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "etag.txt",
        b"etag-body",
        content_type="text/plain",
    )
    saved = storage.save_public(uploaded_file, resource_id=101, filename=uploaded_file.name)

    initial_response = api_client.get(f"/api/storage/public/{saved.path}/")
    etag = initial_response["ETag"]

    response = api_client.get(
        f"/api/storage/public/{saved.path}/",
        HTTP_IF_NONE_MATCH=etag,
    )

    assert response.status_code == 304
    assert response["ETag"] == etag


@pytest.mark.django_db
def test_public_file_route_supports_byte_ranges(storage_test_env, api_client):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "range.txt",
        b"public notes",
        content_type="text/plain",
    )
    saved = storage.save_public(uploaded_file, resource_id=102, filename=uploaded_file.name)

    response = api_client.get(
        f"/api/storage/public/{saved.path}/",
        HTTP_RANGE="bytes=0-5",
    )

    assert response.status_code == 206
    assert response["Content-Range"] == "bytes 0-5/12"
    assert response["Content-Length"] == "6"
    assert response.content == b"public"


@pytest.mark.django_db
def test_public_file_route_rejects_invalid_range(storage_test_env, api_client):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "range-invalid.txt",
        b"public notes",
        content_type="text/plain",
    )
    saved = storage.save_public(uploaded_file, resource_id=103, filename=uploaded_file.name)

    response = api_client.get(
        f"/api/storage/public/{saved.path}/",
        HTTP_RANGE="bytes=50-60",
    )

    assert response.status_code == 416
    assert response["Content-Range"] == "bytes */12"


@pytest.mark.django_db
def test_private_file_route_streams_local_file_for_owner(storage_test_env, authenticated_client, user):
    storage = get_storage_service()
    uploaded_file = SimpleUploadedFile(
        "private-notes.txt",
        b"private notes",
        content_type="text/plain",
    )
    saved = storage.save_private(
        uploaded_file,
        user_id=user.id,
        filename=uploaded_file.name,
        category=FileCategory.PERSONAL,
    )

    response = authenticated_client.get(f"/api/storage/private/{saved.path}/?download=1")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert "attachment" in response["Content-Disposition"]
    assert b"".join(response.streaming_content) == b"private notes"


@pytest.mark.django_db
def test_personal_file_route_logs_open_activity(storage_test_env, authenticated_client, user):
    from apps.resources.models import PersonalResource

    personal_file = PersonalResource.objects.create(
        user=user,
        title="Tracked Personal File",
        file=SimpleUploadedFile("tracked-personal.txt", b"tracked-body"),
    )

    response = authenticated_client.get(f"/api/storage/private/{personal_file.file.name}/")

    personal_file.refresh_from_db()
    assert response.status_code == 200
    assert personal_file.last_accessed_at is not None
    assert RecentActivity.objects.filter(
        user=user,
        personal_file=personal_file,
        activity_type=ActivityType.OPENED_PERSONAL_FILE,
    ).count() == 1


@pytest.mark.django_db
def test_personal_file_route_logs_download_once(storage_test_env, authenticated_client, user):
    from apps.resources.models import PersonalResource

    personal_file = PersonalResource.objects.create(
        user=user,
        title="Tracked Download File",
        file=SimpleUploadedFile("tracked-download.txt", b"download-body"),
    )

    first_response = authenticated_client.get(
        f"/api/storage/private/{personal_file.file.name}/?download=1",
    )
    repeat_response = authenticated_client.get(
        f"/api/storage/private/{personal_file.file.name}/?download=1",
    )

    assert first_response.status_code == 200
    assert repeat_response.status_code == 200
    assert Download.objects.filter(user=user, personal_file=personal_file).count() == 1
    assert RecentActivity.objects.filter(
        user=user,
        personal_file=personal_file,
        activity_type=ActivityType.DOWNLOADED_PERSONAL_FILE,
    ).count() == 1


@pytest.mark.django_db
def test_public_file_route_redirects_for_remote_backend(storage_test_env, api_client, monkeypatch):
    class FakeRemoteStorage:
        def exists(self, path):
            return path == "resources/remote/file.pdf"

        def get_metadata(self, path):
            return FileMetadata(
                name="file.pdf",
                size=123,
                content_type="application/pdf",
                path=path,
                url="https://cdn.example.com/file.pdf",
                visibility=FileVisibility.PUBLIC,
                category=FileCategory.RESOURCE,
            )

        def get_local_path(self, path):
            return None

        def get_url(self, path, signed=False, expires=3600, download=False):
            suffix = "?download=1" if download else ""
            return f"https://cdn.example.com/file.pdf{suffix}"

    monkeypatch.setattr(storage_views, "get_storage_service", lambda: FakeRemoteStorage())

    response = api_client.get("/api/storage/public/resources/remote/file.pdf/?download=1")

    assert response.status_code == 302
    assert response["Location"] == "https://cdn.example.com/file.pdf?download=1"


@pytest.mark.django_db
def test_storage_upload_completion_route_is_idempotent(storage_test_env, authenticated_client, user):
    init_response = authenticated_client.post(
        "/api/storage/upload/init/",
        {
            "filename": "draft.txt",
            "file_size": 5,
            "content_type": "text/plain",
            "category": "personal",
        },
        format="json",
    )
    assert init_response.status_code == 200

    upload_payload = init_response.json()
    path = upload_payload["path"]
    checksum = hashlib.md5(b"draft").hexdigest()

    storage = get_storage_service()
    full_path = storage._backend._full_path(path)
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)
    Path(full_path).write_bytes(b"draft")

    complete_response = authenticated_client.post(
        "/api/storage/upload/complete/",
        {
            "upload_id": upload_payload["upload_id"],
            "path": path,
            "checksum": checksum,
        },
        format="json",
    )
    assert complete_response.status_code == 200

    repeat_response = authenticated_client.post(
        "/api/storage/upload/complete/",
        {
            "upload_id": upload_payload["upload_id"],
            "path": path,
            "checksum": checksum,
        },
        format="json",
    )

    storage_record = UserStorage.objects.get(user=user)
    assert repeat_response.status_code == 200
    assert repeat_response.json()["already_completed"] is True
    assert storage_record.used_storage == 5


def test_cloudinary_metadata_parses_context_values(monkeypatch):
    cloudinary_module = types.ModuleType("cloudinary")
    cloudinary_api_module = types.ModuleType("cloudinary.api")

    def fake_resource(path):
        assert path == "private/personal/42/file"
        return {
            "original_filename": "file.pdf",
            "bytes": 123,
            "format": "pdf",
            "secure_url": "https://cdn.example.com/file.pdf",
            "context": {
                "custom": {
                    "visibility": "authenticated",
                    "category": "personal",
                    "user_id": "42",
                    "checksum": "abc123",
                }
            },
        }

    cloudinary_api_module.resource = fake_resource
    monkeypatch.setitem(sys.modules, "cloudinary", cloudinary_module)
    monkeypatch.setitem(sys.modules, "cloudinary.api", cloudinary_api_module)

    backend = CloudinaryStorageBackend()
    metadata = backend.get_metadata("private/personal/42/file")

    assert metadata.visibility == FileVisibility.AUTHENTICATED
    assert metadata.category == FileCategory.PERSONAL
    assert metadata.uploaded_by == 42
    assert metadata.checksum == "abc123"
    assert metadata.url == "https://cdn.example.com/file.pdf"
