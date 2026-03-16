"""
Storage Service for CampusHub.

Provides:
- Unified storage abstraction
- Public/private file handling
- CDN integration
- Storage backends
"""

import hashlib
import json
import logging
import mimetypes
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, BinaryIO

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class StorageType(Enum):
    """Storage types."""
    LOCAL = "local"
    CLOUDINARY = "cloudinary"
    S3 = "s3"
    GOOGLE_CLOUD = "google_cloud"


class FileVisibility(Enum):
    """File visibility types."""
    PUBLIC = "public"
    PRIVATE = "private"
    AUTHENTICATED = "authenticated"
    TEMPORARY = "temporary"


class FileCategory(Enum):
    """File categories."""
    RESOURCE = "resource"
    PERSONAL = "personal"
    AVATAR = "avatar"
    DOCUMENT = "document"
    MEDIA = "media"
    THUMBNAIL = "thumbnail"
    BACKUP = "backup"


@dataclass
class FileMetadata:
    """File metadata."""
    name: str
    size: int
    content_type: str
    path: str
    url: str | None = None
    visibility: FileVisibility = FileVisibility.PRIVATE
    category: FileCategory = FileCategory.DOCUMENT
    uploaded_by: int | None = None
    created_at: datetime = field(default_factory=timezone.now)
    checksum: str | None = None
    expires_at: datetime | None = None
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_public(self) -> bool:
        return self.visibility == FileVisibility.PUBLIC


@dataclass
class StorageResult:
    """Result of storage operation."""
    success: bool
    file: Any = None
    url: str | None = None
    path: str | None = None
    error: str | None = None
    metadata: FileMetadata | None = None
    
    @classmethod
    def ok(cls, file=None, url=None, path=None, metadata=None) -> 'StorageResult':
        return cls(success=True, file=file, url=url, path=path, metadata=metadata)
    
    @classmethod
    def error(cls, error: str) -> 'StorageResult':
        return cls(success=False, error=error)


class StorageBackend(ABC):
    """Abstract storage backend."""
    
    @abstractmethod
    def save(self, file: BinaryIO, path: str, metadata: dict = None) -> StorageResult:
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        pass
    
    @abstractmethod
    def get_url(self, path: str, signed: bool = False, expires: int = 3600) -> str:
        pass
    
    @abstractmethod
    def get_metadata(self, path: str) -> FileMetadata:
        pass

    def get_local_path(self, path: str) -> str | None:
        """Return a local filesystem path when the backend can serve directly."""
        return None


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: str = None):
        self.base_path = base_path or getattr(settings, 'MEDIA_ROOT', '/tmp/campushub/media')

    def _full_path(self, path: str) -> str:
        base_path = os.path.abspath(self.base_path)
        full_path = os.path.abspath(os.path.join(base_path, path))
        if full_path != base_path and not full_path.startswith(f"{base_path}{os.sep}"):
            raise ValueError("Unsafe storage path")
        return full_path

    @staticmethod
    def _metadata_path(full_path: str) -> str:
        return f"{full_path}.meta.json"

    @staticmethod
    def _guess_content_type(path: str, fallback: str = 'application/octet-stream') -> str:
        return mimetypes.guess_type(path)[0] or fallback

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_enum(enum_class, value, default):
        try:
            return enum_class(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_datetime(value: Any, default: datetime | None) -> datetime | None:
        if not value:
            return default
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return default

    def _build_url(self, path: str) -> str:
        media_url = getattr(settings, 'MEDIA_URL', '/media/').rstrip('/')
        return f"{media_url}/{path}"

    def _infer_metadata_values(
        self,
        path: str,
        raw_metadata: dict[str, Any] | None = None,
    ) -> tuple[FileVisibility, FileCategory, int | None]:
        raw_metadata = raw_metadata or {}
        segments = [segment for segment in path.split('/') if segment]

        visibility = self._safe_enum(
            FileVisibility,
            raw_metadata.get('visibility'),
            FileVisibility.PRIVATE,
        )
        category = self._safe_enum(
            FileCategory,
            raw_metadata.get('category'),
            FileCategory.DOCUMENT,
        )
        uploaded_by = self._safe_int(raw_metadata.get('uploaded_by'))

        if segments:
            if segments[0] in {'resources', 'resource'}:
                visibility = FileVisibility.PUBLIC
                category = FileCategory.RESOURCE
                return visibility, category, uploaded_by

            if segments[0] == 'private' and len(segments) >= 3:
                category = self._safe_enum(FileCategory, segments[1], category)
                uploaded_by = self._safe_int(segments[2]) or uploaded_by
                visibility = FileVisibility.PRIVATE
            elif len(segments) >= 2:
                category = self._safe_enum(FileCategory, segments[0], category)
                uploaded_by = self._safe_int(segments[1]) or uploaded_by
                if uploaded_by is not None and visibility == FileVisibility.PUBLIC:
                    visibility = FileVisibility.PRIVATE

        return visibility, category, uploaded_by

    def _write_metadata_file(self, full_path: str, metadata: dict[str, Any]) -> None:
        metadata_path = self._metadata_path(full_path)
        with open(metadata_path, 'w', encoding='utf-8') as metadata_file:
            json.dump(metadata, metadata_file, sort_keys=True)

    def _read_metadata_file(self, full_path: str) -> dict[str, Any]:
        metadata_path = self._metadata_path(full_path)
        if not os.path.exists(metadata_path):
            return {}

        try:
            with open(metadata_path, 'r', encoding='utf-8') as metadata_file:
                return json.load(metadata_file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read metadata file for %s: %s", full_path, exc)
            return {}

    def _build_file_metadata(
        self,
        path: str,
        full_path: str,
        raw_metadata: dict[str, Any] | None = None,
    ) -> FileMetadata:
        stat = os.stat(full_path)
        raw_metadata = raw_metadata or {}
        visibility, category, uploaded_by = self._infer_metadata_values(path, raw_metadata)
        default_created_at = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.get_current_timezone(),
        )

        return FileMetadata(
            name=raw_metadata.get('name') or os.path.basename(path),
            size=self._safe_int(raw_metadata.get('size')) or stat.st_size,
            content_type=raw_metadata.get('content_type') or self._guess_content_type(path),
            path=path,
            url=self._build_url(path),
            visibility=visibility,
            category=category,
            uploaded_by=uploaded_by,
            created_at=self._parse_datetime(raw_metadata.get('created_at'), default_created_at),
            checksum=raw_metadata.get('checksum'),
            expires_at=self._parse_datetime(raw_metadata.get('expires_at'), None),
        )
    
    def save(self, file: BinaryIO, path: str, metadata: dict = None) -> StorageResult:
        try:
            full_path = self._full_path(path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            file_bytes = StorageService._coerce_file_bytes(file)
            with open(full_path, 'wb') as f:
                f.write(file_bytes)

            metadata = metadata or {}
            stored_metadata = {
                'name': metadata.get('name') or os.path.basename(path),
                'size': len(file_bytes),
                'content_type': metadata.get('content_type') or self._guess_content_type(path),
                'visibility': metadata.get('visibility'),
                'category': metadata.get('category'),
                'uploaded_by': metadata.get('user_id'),
                'checksum': metadata.get('checksum'),
                'created_at': timezone.now().isoformat(),
            }
            self._write_metadata_file(full_path, stored_metadata)

            return StorageResult.ok(
                path=path,
                url=self._build_url(path),
                metadata=self._build_file_metadata(path, full_path, stored_metadata),
            )
        except Exception as e:
            logger.error(f"Local storage save error: {e}")
            return StorageResult.error(str(e))
    
    def delete(self, path: str) -> bool:
        try:
            full_path = self._full_path(path)
            if os.path.exists(full_path):
                os.remove(full_path)
            metadata_path = self._metadata_path(full_path)
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            return True
        except Exception as e:
            logger.error(f"Local storage delete error: {e}")
            return False
    
    def exists(self, path: str) -> bool:
        try:
            full_path = self._full_path(path)
        except ValueError:
            return False
        return os.path.exists(full_path)
    
    def get_url(self, path: str, signed: bool = False, expires: int = 3600) -> str:
        return self._build_url(path)
    
    def get_metadata(self, path: str) -> FileMetadata:
        full_path = self._full_path(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")

        stored_metadata = self._read_metadata_file(full_path)
        return self._build_file_metadata(path, full_path, stored_metadata)

    def get_local_path(self, path: str) -> str | None:
        full_path = self._full_path(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        return full_path


class CloudinaryStorageBackend(StorageBackend):
    """Cloudinary storage backend."""
    
    def __init__(self):
        self.cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
        self.api_key = getattr(settings, 'CLOUDINARY_API_KEY', '')
    
    def save(self, file: BinaryIO, path: str, metadata: dict = None) -> StorageResult:
        try:
            from cloudinary.uploader import upload
            from cloudinary.utils import cloudinary_url

            upload_options = {}
            if metadata:
                upload_options['context'] = {
                    key: str(value)
                    for key, value in metadata.items()
                    if value is not None
                }

            result = upload(
                file,
                public_id=path.replace('.', '_'),
                resource_type='auto',
                **upload_options,
            )
            
            url, _ = cloudinary_url(result['public_id'], resource_type=result['resource_type'])
            
            return StorageResult.ok(
                path=result['public_id'],
                url=url,
                metadata=FileMetadata(
                    name=result.get('original_filename', path),
                    size=result.get('bytes', 0),
                    content_type=result.get('format', ''),
                    path=result['public_id'],
                    url=url,
                )
            )
        except Exception as e:
            logger.error(f"Cloudinary save error: {e}")
            return StorageResult.error(str(e))
    
    def delete(self, path: str) -> bool:
        try:
            from cloudinary.uploader import destroy
            result = destroy(path)
            return result.get('result') == 'ok'
        except Exception as e:
            logger.error(f"Cloudinary delete error: {e}")
            return False
    
    def exists(self, path: str) -> bool:
        try:
            from cloudinary.api import resource
            resource(path)
            return True
        except Exception:
            return False
    
    def get_url(self, path: str, signed: bool = False, expires: int = 3600) -> str:
        from cloudinary.utils import cloudinary_url
        options = {}
        if signed:
            options['sign_url'] = True
            options['expires_at'] = int(time.time()) + expires
        url, _ = cloudinary_url(path, **options)
        return url
    
    def get_metadata(self, path: str) -> FileMetadata:
        from cloudinary.api import resource
        result = resource(path)
        raw_context = result.get('context') or {}
        if isinstance(raw_context, dict) and 'custom' in raw_context:
            raw_context = raw_context.get('custom') or {}

        return FileMetadata(
            name=result.get('original_filename', path),
            size=result.get('bytes', 0),
            content_type=result.get('format', ''),
            path=path,
            url=result.get('secure_url', ''),
            visibility=LocalStorageBackend._safe_enum(
                FileVisibility,
                raw_context.get('visibility'),
                FileVisibility.PRIVATE,
            ),
            category=LocalStorageBackend._safe_enum(
                FileCategory,
                raw_context.get('category'),
                FileCategory.DOCUMENT,
            ),
            uploaded_by=LocalStorageBackend._safe_int(raw_context.get('user_id')),
            checksum=raw_context.get('checksum'),
        )


class StorageService:
    """
    Unified storage service.
    
    Features:
    - Multiple backend support
    - Public/private file handling
    - Automatic path generation
    - URL signing
    - File validation
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Initialize backend based on settings
        self._backend = self._get_backend()
        self._initialized = True
    
    def _get_backend(self) -> StorageBackend:
        """Get storage backend based on settings."""
        # Check for Cloudinary
        if getattr(settings, 'CLOUDINARY_CLOUD_NAME', None):
            return CloudinaryStorageBackend()
        
        # Default to local
        return LocalStorageBackend()
    
    @staticmethod
    def generate_path(
        category: FileCategory,
        filename: str,
        user_id: int = None,
        timestamp: bool = True,
    ) -> str:
        """Generate storage path."""
        parts = [category.value]
        
        if user_id:
            parts.append(str(user_id))
        
        if timestamp:
            from django.utils import timezone
            now = timezone.now()
            parts.append(str(now.year))
            parts.append(f"{now.month:02d}")
        
        # Clean filename
        clean_name = re.sub(r'[^\w\s.-]', '', filename)
        clean_name = re.sub(r'[-\s]+', '-', clean_name)
        
        parts.append(clean_name)
        
        return '/'.join(parts)
    
    @staticmethod
    def generate_public_path(
        resource_id: int,
        filename: str,
    ) -> str:
        """Generate public resource path."""
        return f"resources/{resource_id}/{filename}"
    
    @staticmethod
    def generate_private_path(
        user_id: int,
        filename: str,
        category: FileCategory = FileCategory.PERSONAL,
    ) -> str:
        """Generate private user path."""
        return f"private/{category.value}/{user_id}/{filename}"
    
    @staticmethod
    def calculate_checksum(file: BinaryIO) -> str:
        """Calculate file checksum."""
        md5 = hashlib.md5()
        md5.update(StorageService._coerce_file_bytes(file))
        return md5.hexdigest()

    @staticmethod
    def _coerce_file_bytes(file: Any) -> bytes:
        """Read a file-like object into bytes while preserving the cursor when possible."""
        if isinstance(file, bytes):
            return file
        if isinstance(file, bytearray):
            return bytes(file)

        if not hasattr(file, 'read'):
            raise TypeError("File must be bytes or a file-like object")

        original_position = None
        if hasattr(file, 'tell') and hasattr(file, 'seek'):
            try:
                original_position = file.tell()
                file.seek(0)
            except (OSError, ValueError):
                original_position = None

        try:
            content = file.read()
        finally:
            if original_position is not None:
                try:
                    file.seek(original_position)
                except (OSError, ValueError):
                    pass

        if isinstance(content, str):
            content = content.encode('utf-8')
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("File-like object must return bytes")
        return bytes(content)
    
    def save(
        self,
        file,
        path: str,
        visibility: FileVisibility = FileVisibility.PRIVATE,
        category: FileCategory = FileCategory.DOCUMENT,
        user_id: int = None,
        content_type: str = None,
    ) -> StorageResult:
        """Save file to storage."""
        # Validate file
        if not file:
            return StorageResult.error("No file provided")

        try:
            file_bytes = self._coerce_file_bytes(file)
        except (TypeError, OSError, ValueError) as exc:
            return StorageResult.error(f"Could not read file content: {exc}")

        checksum = self.calculate_checksum(file_bytes)

        # Build metadata
        metadata = {
            'name': getattr(file, 'name', os.path.basename(path)),
            'content_type': content_type or getattr(file, 'content_type', None) or 'application/octet-stream',
            'visibility': visibility.value,
            'category': category.value,
            'user_id': user_id,
            'checksum': checksum,
        }
        
        # Save
        return self._backend.save(file_bytes, path, metadata)
    
    def save_public(self, file, resource_id: int, filename: str) -> StorageResult:
        """Save public resource file."""
        path = self.generate_public_path(resource_id, filename)
        return self.save(
            file,
            path,
            visibility=FileVisibility.PUBLIC,
            category=FileCategory.RESOURCE,
        )
    
    def save_private(
        self,
        file,
        user_id: int,
        filename: str,
        category: FileCategory = FileCategory.PERSONAL,
    ) -> StorageResult:
        """Save private user file."""
        path = self.generate_private_path(user_id, filename, category)
        return self.save(
            file,
            path,
            visibility=FileVisibility.PRIVATE,
            category=category,
            user_id=user_id,
        )
    
    def delete(self, path: str) -> bool:
        """Delete file."""
        return self._backend.delete(path)
    
    def exists(self, path: str) -> bool:
        """Check if file exists."""
        return self._backend.exists(path)
    
    def get_url(
        self,
        path: str,
        signed: bool = False,
        expires: int = 3600,
        download: bool = False,
    ) -> str:
        """Get file URL."""
        url = self._backend.get_url(path, signed, expires)
        
        if download:
            url = f"{url}?download=1"
        
        return url
    
    def get_signed_url(self, path: str, expires: int = 3600) -> str:
        """Get signed URL."""
        return self.get_url(path, signed=True, expires=expires)
    
    def get_public_url(self, path: str) -> str:
        """Get public URL (no signing)."""
        return self.get_url(path, signed=False)
    
    def get_metadata(self, path: str) -> FileMetadata:
        """Get file metadata."""
        return self._backend.get_metadata(path)

    def get_local_path(self, path: str) -> str | None:
        """Return a local filesystem path when the active backend supports it."""
        return self._backend.get_local_path(path)

    def resolve_model_reference(self, path: str) -> dict[str, Any]:
        """Resolve a storage path to a first-class domain object when possible."""
        from apps.resources.models import PersonalResource, Resource

        resource = (
            Resource.objects.select_related("uploaded_by")
            .filter(file=path)
            .first()
        )
        if resource:
            return {"resource": resource, "personal_file": None}

        personal_file = (
            PersonalResource.all_objects.select_related("user")
            .filter(file=path)
            .first()
        )
        if personal_file:
            return {"resource": None, "personal_file": personal_file}

        return {"resource": None, "personal_file": None}

    def calculate_path_checksum(self, path: str) -> str | None:
        """Calculate a checksum for a stored file when the backend supports it."""
        if isinstance(self._backend, LocalStorageBackend):
            full_path = self._backend._full_path(path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"File not found: {path}")

            md5 = hashlib.md5()
            with open(full_path, 'rb') as stored_file:
                for chunk in iter(lambda: stored_file.read(8192), b''):
                    md5.update(chunk)
            return md5.hexdigest()

        metadata = self.get_metadata(path)
        return metadata.checksum

    def verify_checksum(self, path: str, checksum: str) -> bool:
        """Verify a stored file checksum when the backend supports it."""
        actual_checksum = self.calculate_path_checksum(path)
        if not actual_checksum:
            return True
        return actual_checksum == checksum
    
    def get_file_info(self, path: str) -> dict:
        """Get file info (dict format)."""
        metadata = self.get_metadata(path)
        return {
            'name': metadata.name,
            'size': metadata.size,
            'content_type': metadata.content_type,
            'url': metadata.url,
            'is_public': metadata.is_public,
            'created_at': metadata.created_at.isoformat() if metadata.created_at else None,
        }


# Access control
class FileAccessControl:
    """File access control."""
    
    @staticmethod
    def can_access(user, file: FileMetadata) -> bool:
        """Check if user can access file."""
        if file.is_public:
            return True
        
        if not user or not user.is_authenticated:
            return False
        
        if file.visibility == FileVisibility.AUTHENTICATED:
            return True
        
        if file.visibility == FileVisibility.PRIVATE:
            return file.uploaded_by == user.id or user.is_admin
        
        return False
    
    @staticmethod
    def can_delete(user, file: FileMetadata) -> bool:
        """Check if user can delete file."""
        if not user or not user.is_authenticated:
            return False
        
        return file.uploaded_by == user.id or user.is_admin or user.is_moderator
    
    @staticmethod
    def can_upload(user) -> bool:
        """Check if user can upload files."""
        if not user or not user.is_authenticated:
            return False
        return user.is_active


# Storage quota
class StorageQuota:
    """Storage quota management."""
    
    DEFAULT_LIMIT = 5 * 1024 * 1024 * 1024  # 5 GB
    
    @classmethod
    def get_user_limit(cls, user) -> int:
        """Get user's storage limit."""
        from apps.resources.models import UserStorage
        
        try:
            storage = UserStorage.objects.get(user=user)
            return storage.storage_limit
        except UserStorage.DoesNotExist:
            return cls.DEFAULT_LIMIT
    
    @classmethod
    def get_user_usage(cls, user) -> int:
        """Get user's storage usage."""
        from apps.resources.models import UserStorage
        
        try:
            storage = UserStorage.objects.get(user=user)
            return storage.used_storage
        except UserStorage.DoesNotExist:
            return 0
    
    @classmethod
    def can_upload(cls, user, file_size: int) -> tuple[bool, str | None]:
        """Check if user can upload file."""
        usage = cls.get_user_usage(user)
        limit = cls.get_user_limit(user)
        
        if usage + file_size > limit:
            remaining = limit - usage
            return False, f"Storage quota exceeded. {remaining / (1024*1024):.1f}MB remaining."
        
        return True, None
    
    @classmethod
    def get_usage_info(cls, user) -> dict:
        """Get usage info."""
        usage = cls.get_user_usage(user)
        limit = cls.get_user_limit(user)
        
        return {
            'used_bytes': usage,
            'limit_bytes': limit,
            'remaining_bytes': max(0, limit - usage),
            'usage_percent': round((usage / limit * 100) if limit > 0 else 0, 2),
        }


# Singleton instance
_storage_service = None


def get_storage_service() -> StorageService:
    """Get storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
