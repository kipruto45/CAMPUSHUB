"""
Storage API Views for CampusHub.

Provides:
- Public file serving
- Private file access with authentication
- Signed URL generation
- File upload/download endpoints
"""

import hashlib
import os
from dataclasses import replace

from django.core.cache import cache
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.urls import path
from django.utils.http import http_date, parse_http_date_safe
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.authentication import JWTAuthentication
from apps.notifications.models import Notification, NotificationType
from apps.resources.serializers import StorageUpgradeRequestCreateSerializer
from apps.core.storage import (
    FileCategory,
    FileAccessControl,
    FileVisibility,
    StorageQuota,
    get_storage_service,
)

UPLOAD_SESSION_TIMEOUT = 24 * 60 * 60
DELIVERY_AUDIT_WINDOW = 30


def _request_value(request, key, default=None):
    if request.method == 'GET':
        return request.query_params.get(key, default)
    return request.data.get(key, default)


def _parse_positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid integer")

    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")

    return parsed


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _upload_session_cache_key(upload_id: str) -> str:
    return f"storage:upload-session:{upload_id}"


def _delivery_audit_cache_key(user_id, target_kind, target_id, action):
    return f"storage:delivery:{user_id}:{target_kind}:{target_id}:{action}"


def _resolve_storage_target(storage, path):
    resolver = getattr(storage, "resolve_model_reference", None)
    if callable(resolver):
        return resolver(path)
    return {"resource": None, "personal_file": None}


def _enrich_metadata_from_target(metadata, target):
    resource = target.get("resource")
    personal_file = target.get("personal_file")

    if resource:
        visibility = (
            FileVisibility.PUBLIC
            if resource.status == "approved" and resource.is_public
            else FileVisibility.PRIVATE
        )
        return replace(
            metadata,
            visibility=visibility,
            category=FileCategory.RESOURCE,
            uploaded_by=resource.uploaded_by_id,
            name=resource.file.name.split("/")[-1] if resource.file else metadata.name,
            size=resource.file_size or metadata.size,
        )

    if personal_file:
        visibility = (
            FileVisibility.AUTHENTICATED
            if personal_file.visibility == "shared_link"
            else FileVisibility.PRIVATE
        )
        return replace(
            metadata,
            visibility=visibility,
            category=FileCategory.PERSONAL,
            uploaded_by=personal_file.user_id,
            name=personal_file.file.name.split("/")[-1] if personal_file.file else metadata.name,
            size=personal_file.file_size or metadata.size,
        )

    return metadata


def _can_access_target(user, target, *, public_endpoint):
    resource = target.get("resource")
    personal_file = target.get("personal_file")

    if resource:
        if public_endpoint:
            return resource.status == "approved" and resource.is_public

        if resource.status == "approved":
            return True

        if not user or not user.is_authenticated:
            return False

        return (
            resource.uploaded_by_id == user.id
            or user.is_admin
            or user.is_moderator
        )

    if personal_file:
        if public_endpoint:
            return False

        if personal_file.is_deleted:
            return False

        if not user or not user.is_authenticated:
            return False

        if personal_file.visibility == "shared_link":
            return True

        return (
            personal_file.user_id == user.id
            or user.is_admin
            or user.is_moderator
        )

    return None


def _update_profile_downloads(user):
    if not user or not user.is_authenticated:
        return

    from apps.accounts.models import Profile

    Profile.objects.filter(user=user).update(total_downloads=F("total_downloads") + 1)


def _record_resource_download(user, resource, request):
    from apps.activity.services import ActivityService
    from apps.core.utils import get_client_ip, get_user_agent
    from apps.downloads.models import Download
    from apps.resources.models import Resource

    Download.objects.create(
        user=user,
        resource=resource,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    Resource.objects.filter(pk=resource.pk).update(download_count=F("download_count") + 1)
    _update_profile_downloads(user)
    ActivityService.log_download(user=user, resource=resource, request=request)


def _record_personal_file_download(user, personal_file, request):
    from apps.activity.services import ActivityService
    from apps.core.utils import get_client_ip, get_user_agent
    from apps.downloads.models import Download

    Download.objects.create(
        user=user,
        personal_file=personal_file,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    _update_profile_downloads(user)
    ActivityService.log_download(user=user, personal_file=personal_file, request=request)


def _record_personal_file_open(user, personal_file, request):
    from apps.activity.services import ActivityService

    personal_file.mark_accessed()
    ActivityService.log_personal_file_open(user=user, personal_file=personal_file, request=request)


def _audit_storage_delivery(request, target, *, download):
    if request.method != "GET":
        return

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return

    resource = target.get("resource")
    personal_file = target.get("personal_file")

    if resource and download and resource.status == "approved":
        cache_key = _delivery_audit_cache_key(user.id, "resource", resource.id, "download")
        if cache.get(cache_key):
            return
        _record_resource_download(user, resource, request)
        cache.set(cache_key, True, timeout=DELIVERY_AUDIT_WINDOW)
        return

    if personal_file:
        action = "download" if download else "open"
        cache_key = _delivery_audit_cache_key(user.id, "personal_file", personal_file.id, action)
        if cache.get(cache_key):
            return

        if download:
            _record_personal_file_download(user, personal_file, request)
        else:
            _record_personal_file_open(user, personal_file, request)

        cache.set(cache_key, True, timeout=DELIVERY_AUDIT_WINDOW)


def _build_etag(metadata, stat_result):
    if metadata.checksum:
        return f'"{metadata.checksum}"'

    fingerprint = f"{metadata.path}:{stat_result.st_size}:{stat_result.st_mtime_ns}"
    return f'"{hashlib.md5(fingerprint.encode("utf-8")).hexdigest()}"'


def _apply_standard_file_headers(response, metadata, stat_result, etag, *, download):
    response["ETag"] = etag
    response["Last-Modified"] = http_date(stat_result.st_mtime)
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(stat_result.st_size)
    cache_scope = "public" if metadata.is_public else "private"
    response["Cache-Control"] = f"{cache_scope}, max-age=3600, must-revalidate"
    if download and metadata.name:
        response["Content-Disposition"] = f'attachment; filename="{metadata.name}"'
    return response


def _is_not_modified(request, etag, stat_result):
    if_none_match = request.META.get("HTTP_IF_NONE_MATCH")
    if if_none_match and if_none_match.strip() == etag:
        return True

    if_modified_since = request.META.get("HTTP_IF_MODIFIED_SINCE")
    if if_modified_since:
        parsed = parse_http_date_safe(if_modified_since)
        if parsed >= int(stat_result.st_mtime):
            return True

    return False


def _parse_range_header(range_header, file_size):
    if not range_header or not range_header.startswith("bytes="):
        return None

    range_spec = range_header.split("=", 1)[1].strip()
    if "," in range_spec:
        raise ValueError("Multiple byte ranges are not supported")

    start_str, sep, end_str = range_spec.partition("-")
    if not sep:
        raise ValueError("Invalid byte range")

    if start_str == "":
        if not end_str:
            raise ValueError("Invalid byte range")
        suffix_length = int(end_str)
        if suffix_length <= 0:
            raise ValueError("Invalid byte range")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1

    if start < 0 or end < start or start >= file_size:
        raise ValueError("Requested range is not satisfiable")

    end = min(end, file_size - 1)
    return start, end


def _build_head_response(metadata, stat_result, etag, *, download, status_code=200, content_length=None, content_range=None):
    response = HttpResponse(status=status_code, content_type=metadata.content_type or "application/octet-stream")
    _apply_standard_file_headers(response, metadata, stat_result, etag, download=download)
    response["Content-Length"] = str(content_length if content_length is not None else stat_result.st_size)
    if content_range:
        response["Content-Range"] = content_range
    return response


def _build_partial_file_response(local_path, metadata, stat_result, etag, start, end, *, download, head_only=False):
    content_length = end - start + 1
    content_range = f"bytes {start}-{end}/{stat_result.st_size}"

    if head_only:
        return _build_head_response(
            metadata,
            stat_result,
            etag,
            download=download,
            status_code=206,
            content_length=content_length,
            content_range=content_range,
        )

    with open(local_path, "rb") as stored_file:
        stored_file.seek(start)
        payload = stored_file.read(content_length)

    response = HttpResponse(
        payload,
        status=206,
        content_type=metadata.content_type or "application/octet-stream",
    )
    _apply_standard_file_headers(response, metadata, stat_result, etag, download=download)
    response["Content-Length"] = str(content_length)
    response["Content-Range"] = content_range
    return response


def _stream_local_file(request, local_path, metadata, *, download):
    stat_result = os.stat(local_path)
    etag = _build_etag(metadata, stat_result)

    if _is_not_modified(request, etag, stat_result):
        response = HttpResponse(status=304)
        response["ETag"] = etag
        response["Last-Modified"] = http_date(stat_result.st_mtime)
        response["Cache-Control"] = (
            "public, max-age=3600, must-revalidate"
            if metadata.is_public
            else "private, max-age=3600, must-revalidate"
        )
        return response

    range_header = request.META.get("HTTP_RANGE")
    if range_header:
        try:
            start, end = _parse_range_header(range_header, stat_result.st_size)
        except (TypeError, ValueError):
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{stat_result.st_size}"
            response["Accept-Ranges"] = "bytes"
            return response

        return _build_partial_file_response(
            local_path,
            metadata,
            stat_result,
            etag,
            start,
            end,
            download=download,
            head_only=request.method == "HEAD",
        )

    if request.method == "HEAD":
        return _build_head_response(
            metadata,
            stat_result,
            etag,
            download=download,
        )

    response = FileResponse(
        open(local_path, "rb"),
        as_attachment=download,
        filename=metadata.name or None,
        content_type=metadata.content_type or "application/octet-stream",
    )
    _apply_standard_file_headers(response, metadata, stat_result, etag, download=download)
    return response


def _serve_or_redirect_file(request, storage, path, metadata, *, signed: bool):
    download = _parse_bool(request.query_params.get('download', False))
    target = _resolve_storage_target(storage, path)
    _audit_storage_delivery(request, target, download=download)

    try:
        local_path = storage.get_local_path(path)
    except (FileNotFoundError, OSError, ValueError):
        local_path = None

    if local_path:
        return _stream_local_file(request, local_path, metadata, download=download)

    url = storage.get_url(path, signed=signed, expires=3600, download=download)
    return HttpResponseRedirect(url)


@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def serve_public_file(request, path):
    """
    Serve a public file directly for local storage or redirect for remote storage.
    
    URL: /api/storage/public/<path>/
    """
    storage = get_storage_service()
    
    if not storage.exists(path):
        raise Http404("File not found")
    
    # Get file metadata
    try:
        metadata = storage.get_metadata(path)
    except (FileNotFoundError, OSError, ValueError):
        metadata = None

    if not metadata:
        return Response(
            {"error": "File metadata not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    target = _resolve_storage_target(storage, path)
    metadata = _enrich_metadata_from_target(metadata, target)
    target_access = _can_access_target(None, target, public_endpoint=True)
    if target_access is False:
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if target_access is None and not metadata.is_public:
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN
        )

    return _serve_or_redirect_file(
        request,
        storage,
        path,
        metadata,
        signed=False,
    )


@api_view(['GET', 'HEAD'])
@permission_classes([IsAuthenticated])
def serve_private_file(request, path):
    """
    Serve a private file directly for local storage or redirect for remote storage.
    
    URL: /api/storage/private/<path>/
    """
    storage = get_storage_service()
    
    if not storage.exists(path):
        raise Http404("File not found")
    
    # Get metadata
    try:
        metadata = storage.get_metadata(path)
    except (FileNotFoundError, OSError, ValueError):
        return Response(
            {"error": "File metadata not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    target = _resolve_storage_target(storage, path)
    metadata = _enrich_metadata_from_target(metadata, target)
    target_access = _can_access_target(request.user, target, public_endpoint=False)
    if target_access is False:
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    if target_access is None and not FileAccessControl.can_access(request.user, metadata):
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    return _serve_or_redirect_file(
        request,
        storage,
        path,
        metadata,
        signed=True,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def get_signed_url(request):
    """
    Generate signed URL for private file.
    
    POST /api/storage/sign/
    {
        "path": "private/personal/1/file.pdf",
        "expires": 3600,  # seconds (optional)
        "download": true   # optional
    }
    """
    path = _request_value(request, 'path')
    if not path:
        return Response(
            {"error": "Path is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    storage = get_storage_service()
    
    if not storage.exists(path):
        raise Http404("File not found")
    
    # Get metadata
    try:
        metadata = storage.get_metadata(path)
    except (FileNotFoundError, OSError, ValueError):
        return Response(
            {"error": "File metadata not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    target = _resolve_storage_target(storage, path)
    metadata = _enrich_metadata_from_target(metadata, target)
    target_access = _can_access_target(request.user, target, public_endpoint=False)
    if target_access is False:
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    if target_access is None and not FileAccessControl.can_access(request.user, metadata):
        return Response(
            {"error": "Access denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Generate signed URL
    try:
        expires = _parse_positive_int(_request_value(request, 'expires', 3600), 'expires')
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    download = _parse_bool(_request_value(request, 'download', False))
    
    url = storage.get_url(path, signed=True, expires=expires, download=download)
    
    return Response({
        "path": path,
        "url": url,
        "expires_in": expires,
        "download": download,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_storage_quota(request):
    """
    Check user's storage quota.
    
    GET /api/storage/quota/
    """
    info = StorageQuota.get_usage_info(request.user)
    return Response(info)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_upload(request):
    """
    Validate if user can upload file.
    
    POST /api/storage/validate/
    {
        "file_size": 10485760  # bytes
    }
    """
    try:
        file_size = _parse_positive_int(request.data.get('file_size', 0), 'file_size')
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    can_upload, message = StorageQuota.can_upload(request.user, file_size)
    
    if can_upload:
        return Response({
            "allowed": True,
            "file_size": file_size,
        })
    else:
        return Response(
            {"allowed": False, "error": message},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_upload(request):
    """
    Initiate multipart upload.
    
    POST /api/storage/upload/init/
    {
        "filename": "document.pdf",
        "file_size": 10485760,
        "content_type": "application/pdf",
        "category": "personal"
    }
    """
    filename = request.data.get('filename')
    file_size = request.data.get('file_size')
    content_type = request.data.get('content_type', 'application/octet-stream')
    category = request.data.get('category', 'personal')
    
    if not filename or not file_size:
        return Response(
            {"error": "Filename and file_size are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        file_size = _parse_positive_int(file_size, 'file_size')
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    can_upload, message = StorageQuota.can_upload(request.user, file_size)
    if not can_upload:
        return Response(
            {"error": message},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check can upload permission
    if not FileAccessControl.can_upload(request.user):
        return Response(
            {"error": "You don't have permission to upload files"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    storage = get_storage_service()

    try:
        category_enum = FileCategory(category)
    except ValueError:
        return Response(
            {"error": "Invalid file category"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    path = storage.generate_path(
        category=category_enum,
        filename=filename,
        user_id=request.user.id,
    )
    
    # Generate upload ID and presigned URL
    import uuid
    upload_id = str(uuid.uuid4())

    cache.set(
        _upload_session_cache_key(upload_id),
        {
            "upload_id": upload_id,
            "user_id": request.user.id,
            "path": path,
            "file_size": file_size,
            "content_type": content_type,
            "category": category_enum.value,
            "completed": False,
            "created_at": timezone.now().isoformat(),
        },
        timeout=UPLOAD_SESSION_TIMEOUT,
    )
    
    return Response({
        "upload_id": upload_id,
        "path": path,
        "url": storage.get_signed_url(path, expires=3600),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_upload(request):
    """
    Complete multipart upload.
    
    POST /api/storage/upload/complete/
    {
        "upload_id": "uuid",
        "path": "personal/1/file.pdf",
        "checksum": "md5hash"
    }
    """
    upload_id = request.data.get('upload_id')
    path = request.data.get('path')
    checksum = request.data.get('checksum')
    
    if not upload_id or not path:
        return Response(
            {"error": "upload_id and path are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    session = cache.get(_upload_session_cache_key(upload_id))
    if not session:
        return Response(
            {"error": "Upload session is invalid or expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if session.get("user_id") != request.user.id:
        return Response(
            {"error": "Upload session does not belong to the authenticated user"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if session.get("path") != path:
        return Response(
            {"error": "Upload path does not match the initiated upload session"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    storage = get_storage_service()
    
    if not storage.exists(path):
        return Response(
            {"error": "File not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        metadata = storage.get_metadata(path)
    except (FileNotFoundError, OSError, ValueError):
        return Response(
            {"error": "File metadata not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if checksum and not storage.verify_checksum(path, checksum):
        return Response(
            {"error": "Checksum verification failed"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if session.get("completed"):
        return Response({
            "success": True,
            "path": path,
            "url": storage.get_signed_url(path),
            "already_completed": True,
            "file_size": metadata.size,
        })

    from apps.resources.models import UserStorage

    storage_obj, _ = UserStorage.objects.get_or_create(user=request.user)
    UserStorage.objects.filter(pk=storage_obj.pk).update(
        used_storage=F('used_storage') + metadata.size
    )

    session.update(
        {
            "completed": True,
            "completed_at": timezone.now().isoformat(),
            "stored_file_size": metadata.size,
            "checksum": checksum or storage.calculate_path_checksum(path),
        }
    )
    cache.set(
        _upload_session_cache_key(upload_id),
        session,
        timeout=UPLOAD_SESSION_TIMEOUT,
    )
    
    return Response({
        "success": True,
        "path": path,
        "url": storage.get_signed_url(path),
        "file_size": metadata.size,
    })


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def request_storage_upgrade(request):
    """Create a storage upgrade request for the current user."""
    serializer = StorageUpgradeRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    upgrade_request = serializer.save(user=request.user, status="pending")

    # Notify admins
    try:
        from apps.accounts.models import User

        admins = User.objects.filter(is_staff=True, is_active=True).exclude(
            id=request.user.id
        )
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=admin,
                    title="Storage Upgrade Request",
                    message=f"{request.user.full_name or request.user.email} requested {upgrade_request.plan} storage.",
                    notification_type=NotificationType.SYSTEM,
                    link="/(admin)/dashboard",
                )
                for admin in admins
            ]
        )
    except Exception:
        pass

    return Response(
        {
            "id": str(upgrade_request.id),
            "status": upgrade_request.status,
            "plan": upgrade_request.plan,
            "billing_cycle": upgrade_request.billing_cycle,
        },
        status=status.HTTP_201_CREATED,
    )


# URL patterns for include
urlpatterns = [
    # Public file serving
    path('public/<path:path>/', serve_public_file, name='serve_public_file'),
    # Private file serving
    path('private/<path:path>/', serve_private_file, name='serve_private_file'),
    # Signed URL
    path('sign/', get_signed_url, name='get_signed_url'),
    # Quota
    path('quota/', check_storage_quota, name='check_storage_quota'),
    # Validate upload
    path('validate/', validate_upload, name='validate_upload'),
    # Upload initiation
    path('upload/init/', initiate_upload, name='initiate_upload'),
    # Upload completion
    path('upload/complete/', complete_upload, name='complete_upload'),
]
