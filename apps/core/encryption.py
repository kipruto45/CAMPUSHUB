"""
End-to-end encryption service for sensitive data at rest in CampusHub.

This module provides:
- AES-256-GCM encryption for sensitive fields
- Key derivation from user-specific keys + master key
- Encrypted field mixin for Django models
- Key rotation functionality
- Graceful degradation for migration

Usage:
    # Basic encryption/decryption
    from apps.core.encryption import EncryptionService
    encrypted = EncryptionService.encrypt("sensitive data")
    decrypted = EncryptionService.decrypt(encrypted)

    # With user-specific key derivation
    encrypted = EncryptionService.encrypt("sensitive data", user_id=123)
    decrypted = EncryptionService.decrypt(encrypted, user_id=123)

    # With a Django model
    from apps.core.encryption import EncryptedFieldMixin
    class MyModel(EncryptedFieldMixin, models.Model):
        sensitive_field = encrypted_charfield()
"""

import base64
import hashlib
import json
import logging
import os
import warnings
from datetime import date, datetime
from typing import Any, Iterable, Optional, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption errors."""
    pass


class EncryptionKeyError(EncryptionError):
    """Exception raised when encryption key is invalid or missing."""
    pass


class EncryptionDecryptionError(EncryptionError):
    """Exception raised when encryption/decryption fails."""
    pass


class KeyRotationError(EncryptionError):
    """Exception raised when key rotation fails."""
    pass


class EncryptionService:
    """
    AES-256-GCM encryption service for sensitive data at rest.
    
    This service provides:
    - Field-level encryption using AES-256-GCM
    - User-specific key derivation
    - Key rotation support
    - Graceful degradation for migration
    """

    # AES block size (for GCM, we use 12-byte IV / 96-bit nonce)
    IV_SIZE = 12
    # Authentication tag size (16 bytes / 128 bits for GCM)
    TAG_SIZE = 16
    # Key size (32 bytes / 256 bits for AES-256)
    KEY_SIZE = 32

    # Encrypted data format: version (1 byte) + IV (12 bytes) + ciphertext + tag (16 bytes)
    _VERSION_OFFSET = 0
    _IV_OFFSET = 1
    _TAG_OFFSET = -16  # Last 16 bytes

    # Current encryption version fallback
    CURRENT_VERSION = 1

    # Cache for derived keys
    _key_cache: dict = {}

    FALLBACK_PREFIX = "__UNENCRYPTED__"

    @classmethod
    def get_current_version(cls) -> int:
        """Return the configured encryption key version."""
        return int(getattr(settings, "ENCRYPTION_KEY_VERSION", cls.CURRENT_VERSION) or cls.CURRENT_VERSION)

    @classmethod
    def _normalize_key_hex(cls, key_hex: str) -> str:
        return str(key_hex or "").strip()

    @classmethod
    def _parse_master_key_hex(cls, key_hex: str) -> bytes:
        """Parse and validate a hex-encoded master key."""
        normalized = cls._normalize_key_hex(key_hex)
        if not normalized:
            raise EncryptionKeyError("Encryption master key is not configured.")

        try:
            key_bytes = bytes.fromhex(normalized)
        except ValueError as exc:
            raise EncryptionKeyError(
                "ENCRYPTION_MASTER_KEY must be a valid hex string. "
                f"Expected 64 hex characters (32 bytes), got {len(normalized)} characters."
            ) from exc

        if len(key_bytes) < cls.KEY_SIZE:
            raise EncryptionKeyError(
                f"ENCRYPTION_MASTER_KEY must be at least {cls.KEY_SIZE * 2} hex characters "
                f"({cls.KEY_SIZE} bytes) for AES-256 encryption."
            )

        return key_bytes[: cls.KEY_SIZE]

    @classmethod
    def _get_master_key(cls) -> bytes:
        """Get the master encryption key from settings."""
        return cls._parse_master_key_hex(getattr(settings, "ENCRYPTION_MASTER_KEY", ""))

    @classmethod
    def _get_key_salt(cls) -> bytes:
        """Get the salt for key derivation."""
        salt = settings.ENCRYPTION_KEY_SALT
        if not salt:
            raise EncryptionKeyError(
                "ENCRYPTION_KEY_SALT is not set. "
                "Please configure ENCRYPTION_KEY_SALT in your settings."
            )
        return salt.encode('utf-8')

    @classmethod
    def has_master_key(cls) -> bool:
        """Check whether a usable current master key is configured."""
        try:
            cls._get_master_key()
            return True
        except EncryptionKeyError:
            return False

    @classmethod
    def _parse_previous_master_keys(cls) -> list[tuple[int, bytes]]:
        """Return previously configured master keys for decryption during rotation."""
        entries: list[tuple[int, bytes]] = []
        previous_keys = str(getattr(settings, "ENCRYPTION_PREVIOUS_KEYS", "") or "").strip()
        if not previous_keys:
            return entries

        for raw_entry in previous_keys.split(","):
            key_entry = raw_entry.strip()
            if not key_entry:
                continue
            if ":" not in key_entry:
                logger.warning("Invalid previous encryption key entry: %s", key_entry)
                continue
            version_raw, key_hex = key_entry.split(":", 1)
            try:
                entries.append((int(version_raw), cls._parse_master_key_hex(key_hex)))
            except (ValueError, EncryptionKeyError):
                logger.warning("Invalid previous encryption key entry: %s", key_entry)
        return entries

    @classmethod
    def get_key_ring(cls) -> list[tuple[int, bytes]]:
        """Return the ordered list of active and previous master keys."""
        key_ring: list[tuple[int, bytes]] = []
        try:
            key_ring.append((cls.get_current_version(), cls._get_master_key()))
        except EncryptionKeyError:
            pass

        seen_versions = {version for version, _ in key_ring}
        for version, key_bytes in cls._parse_previous_master_keys():
            if version in seen_versions:
                continue
            key_ring.append((version, key_bytes))
            seen_versions.add(version)
        return key_ring

    @classmethod
    def has_decryption_keys(cls) -> bool:
        """Check whether any usable key material is available for decrypting data."""
        return bool(cls.get_key_ring())

    @classmethod
    def _derive_key(cls, master_key: bytes, user_id: Optional[int] = None, 
                    context: Optional[str] = None) -> bytes:
        """
        Derive an encryption key from the master key.
        
        Args:
            master_key: The master encryption key
            user_id: Optional user ID for user-specific key derivation
            context: Optional context string for additional key derivation
            
        Returns:
            Derived 256-bit key
        """
        cache_key = f"{master_key.hex()}:{user_id}:{context}"
        
        # Check cache for derived key
        if cache_key in cls._key_cache:
            return cls._key_cache[cache_key]
        
        # Derive key using HKDF-like construction with SHA-256
        salt = cls._get_key_salt()
        
        if user_id is not None:
            # User-specific key derivation
            info = f"campushub:user:{user_id}"
            if context:
                info += f":{context}"
            
            # Use PBKDF2-like derivation
            key_material = master_key + salt + str(user_id).encode('utf-8')
            if context:
                key_material += context.encode('utf-8')
            
            derived_key = hashlib.pbkdf2_hmac(
                'sha256',
                key_material,
                salt,
                iterations=100000,  # High iteration count for security
                dklen=cls.KEY_SIZE
            )
        else:
            # Master-only key derivation
            info = "campushub:master"
            if context:
                info += f":{context}"
            
            key_material = master_key + salt
            if context:
                key_material += context.encode('utf-8')
            
            derived_key = hashlib.pbkdf2_hmac(
                'sha256',
                key_material,
                salt,
                iterations=100000,
                dklen=cls.KEY_SIZE
            )
        
        # Cache the derived key
        cls._key_cache[cache_key] = derived_key
        
        return derived_key

    @classmethod
    def _get_cipher(cls, key: bytes, iv: bytes):
        """Get AES-GCM cipher instance."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(key)
        except ImportError:
            raise EncryptionError(
                "cryptography library is required for encryption. "
                "Install it with: pip install cryptography"
            )

    @classmethod
    def _fallback_value(cls, plaintext: Union[str, bytes]) -> str:
        """Return a marked plaintext fallback value."""
        if isinstance(plaintext, bytes):
            plaintext = plaintext.decode("utf-8")
        return f"{cls.FALLBACK_PREFIX}{plaintext}"

    @classmethod
    def is_fallback_plaintext(cls, value: Any) -> bool:
        return isinstance(value, str) and value.startswith(cls.FALLBACK_PREFIX)

    @classmethod
    def unwrap_fallback_plaintext(cls, value: str) -> str:
        return value[len(cls.FALLBACK_PREFIX):]

    @classmethod
    def encrypt(cls, plaintext: Union[str, bytes], user_id: Optional[int] = None,
                context: Optional[str] = None) -> str:
        """
        Encrypt sensitive data using AES-256-GCM.
        
        Args:
            plaintext: The data to encrypt (string or bytes)
            user_id: Optional user ID for user-specific key derivation
            context: Optional context string for additional key derivation
            
        Returns:
            Base64-encoded encrypted data (version + IV + ciphertext + tag)
            
        Raises:
            EncryptionError: If encryption fails
        """
        if plaintext is None:
            return plaintext

        encryption_enabled = bool(getattr(settings, "ENCRYPTION_ENABLED", False))
        allow_fallback = bool(getattr(settings, "ENCRYPTION_ALLOW_FALLBACK", False))
        warn_on_fallback = bool(getattr(settings, "ENCRYPTION_WARN_ON_FALLBACK", True))

        if not encryption_enabled:
            if allow_fallback:
                if warn_on_fallback:
                    warnings.warn(
                        "Encryption is disabled. Returning unencrypted data with fallback marker.",
                        UserWarning,
                    )
                return cls._fallback_value(plaintext)
            raise EncryptionError(
                "Encryption is not enabled. Set ENCRYPTION_ENABLED=True "
                "or set ENCRYPTION_ALLOW_FALLBACK=True to allow unencrypted fallback."
            )

        try:
            # Convert plaintext to bytes if needed
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext

            # Get the master key
            master_key = cls._get_master_key()

            # Derive the encryption key
            key = cls._derive_key(master_key, user_id, context)

            # Generate random IV (12 bytes for GCM)
            iv = os.urandom(cls.IV_SIZE)

            # Get AES-GCM cipher and encrypt
            cipher = cls._get_cipher(key, iv)
            ciphertext_with_tag = cipher.encrypt(iv, plaintext_bytes, None)

            # Format: version (1 byte) + IV (12 bytes) + ciphertext + tag (16 bytes)
            current_version = cls.get_current_version()
            if current_version > 255:
                raise EncryptionError("ENCRYPTION_KEY_VERSION must be between 0 and 255.")
            version_byte = bytes([current_version])
            encrypted_data = version_byte + iv + ciphertext_with_tag

            # Return base64-encoded result
            return base64.b64encode(encrypted_data).decode('utf-8')

        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            if allow_fallback:
                if warn_on_fallback:
                    warnings.warn(
                        f"Encryption failed: {str(e)}. Returning unencrypted data.",
                        UserWarning,
                    )
                return cls._fallback_value(plaintext)
            raise EncryptionDecryptionError(f"Encryption failed: {str(e)}")

    @classmethod
    def decrypt(cls, encrypted_data: str, user_id: Optional[int] = None,
                context: Optional[str] = None) -> str:
        """
        Decrypt sensitive data using AES-256-GCM.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            user_id: Optional user ID for user-specific key derivation
            context: Optional context string for key derivation
            
        Returns:
            Decrypted plaintext (string)
            
        Raises:
            EncryptionError: If decryption fails
        """
        if encrypted_data is None:
            return encrypted_data

        encryption_enabled = bool(getattr(settings, "ENCRYPTION_ENABLED", False))
        allow_fallback = bool(getattr(settings, "ENCRYPTION_ALLOW_FALLBACK", False))
        warn_on_fallback = bool(getattr(settings, "ENCRYPTION_WARN_ON_FALLBACK", True))

        # Check for unencrypted fallback data
        if cls.is_fallback_plaintext(encrypted_data):
            plaintext = cls.unwrap_fallback_plaintext(encrypted_data)
            if encryption_enabled and not allow_fallback:
                raise EncryptionError(
                    "Received unencrypted data but encryption is required."
                )
            return plaintext

        if not cls.is_encrypted(encrypted_data):
            if allow_fallback or not encryption_enabled:
                return encrypted_data
            raise EncryptionDecryptionError("Value does not appear to be encrypted.")

        try:
            # Decode base64
            try:
                encrypted_bytes = base64.b64decode(encrypted_data)
            except Exception:
                # If it's not valid base64, maybe it's plain legacy data
                if allow_fallback:
                    if warn_on_fallback:
                        warnings.warn(
                            "Invalid encrypted data format. Returning as-is.",
                            UserWarning,
                        )
                    return encrypted_data
                raise EncryptionDecryptionError(
                    "Invalid encrypted data format. Not a valid base64 string."
                )

            # Parse the encrypted data format
            # version (1 byte) + IV (12 bytes) + ciphertext + tag (16 bytes)
            if len(encrypted_bytes) < 1 + cls.IV_SIZE + cls.TAG_SIZE:
                raise EncryptionDecryptionError(
                    f"Invalid encrypted data length. Expected at least "
                    f"{1 + cls.IV_SIZE + cls.TAG_SIZE} bytes, got {len(encrypted_bytes)}."
                )

            version = encrypted_bytes[cls._VERSION_OFFSET]
            iv = encrypted_bytes[cls._IV_OFFSET:cls._IV_OFFSET + cls.IV_SIZE]
            ciphertext_with_tag = encrypted_bytes[cls._IV_OFFSET + cls.IV_SIZE:]

            key_ring = cls.get_key_ring()
            if not key_ring:
                if allow_fallback:
                    if warn_on_fallback:
                        warnings.warn(
                            "Encryption keys are unavailable. Returning stored encrypted data as-is.",
                            UserWarning,
                        )
                    return encrypted_data
                raise EncryptionKeyError(
                    "No encryption keys are available for decryption."
                )

            matching_keys = [
                (key_version, master_key)
                for key_version, master_key in key_ring
                if key_version == version
            ]
            fallback_keys = [
                (key_version, master_key)
                for key_version, master_key in key_ring
                if key_version != version
            ]
            keys_to_try = matching_keys + fallback_keys

            # Try decryption with available keys
            last_error = None
            for key_version, master_key in keys_to_try:
                try:
                    key = cls._derive_key(master_key, user_id, context)
                    cipher = cls._get_cipher(key, iv)
                    plaintext_bytes = cipher.decrypt(iv, ciphertext_with_tag, None)
                    
                    # If we used a non-current key, log a warning about key rotation
                    if key_version != cls.get_current_version():
                        if warn_on_fallback:
                            warnings.warn(
                                f"Data was decrypted with key version {key_version}. "
                                "Consider re-encrypting with the current key.",
                                UserWarning,
                            )
                    
                    return plaintext_bytes.decode('utf-8')
                    
                except Exception as e:
                    last_error = e
                    continue

            # All decryption attempts failed
            raise EncryptionDecryptionError(
                f"Decryption failed with all available keys: {str(last_error)}"
            )

        except EncryptionDecryptionError:
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            if allow_fallback:
                if warn_on_fallback:
                    warnings.warn(
                        f"Decryption failed: {str(e)}. Returning encrypted data as-is.",
                        UserWarning,
                    )
                return encrypted_data
            raise EncryptionDecryptionError(f"Decryption failed: {str(e)}")

    @classmethod
    def rotate_key(cls, new_master_key: str, old_master_key: Optional[str] = None) -> bool:
        """
        Rotate to a new master key.
        
        This method helps with key rotation by:
        1. Validating the new key format
        2. Storing the old key for decryption of existing data
        3. Updating the settings with the new key
        
        Args:
            new_master_key: The new master key (hex string)
            old_master_key: Optional old master key to preserve for decryption
            
        Returns:
            True if key rotation was successful
            
        Raises:
            KeyRotationError: If key rotation fails
        """
        try:
            # Validate new key format
            cls._parse_master_key_hex(new_master_key)

            # If old key provided, add it to previous keys
            if old_master_key:
                old_key_hex = cls._parse_master_key_hex(old_master_key).hex()
                
                # Get current version and increment
                current_version = cls.get_current_version()
                new_version = current_version + 1
                
                # Build previous keys string
                prev_keys = getattr(settings, 'ENCRYPTION_PREVIOUS_KEYS', '') or ''
                if prev_keys:
                    prev_keys += ','
                prev_keys += f"{current_version}:{old_key_hex}"
                
                # Update settings (these won't persist across restarts without database storage)
                settings.ENCRYPTION_PREVIOUS_KEYS = prev_keys
                settings.ENCRYPTION_KEY_VERSION = new_version

            # Update master key
            settings.ENCRYPTION_MASTER_KEY = new_master_key
            
            # Clear key cache
            cls._key_cache.clear()
            
            logger.info(f"Key rotation completed. New version: {settings.ENCRYPTION_KEY_VERSION}")
            return True

        except ValueError as e:
            raise KeyRotationError(f"Invalid key format: {str(e)}")
        except Exception as e:
            raise KeyRotationError(f"Key rotation failed: {str(e)}")

    @classmethod
    def re_encrypt(cls, encrypted_data: str, user_id: Optional[int] = None,
                   context: Optional[str] = None) -> str:
        """
        Re-encrypt data with the current key.
        
        This is useful after key rotation to update encrypted data
        with the new encryption key.
        
        Args:
            encrypted_data: The encrypted data to re-encrypt
            user_id: Optional user ID
            context: Optional context
            
        Returns:
            Re-encrypted data
        """
        if encrypted_data is None:
            return encrypted_data

        plaintext = cls.decrypt(encrypted_data, user_id, context)
        return cls.encrypt(plaintext, user_id, context)

    @classmethod
    def is_encrypted(cls, data: str) -> bool:
        """
        Check if data appears to be encrypted.
        
        Args:
            data: The data to check
            
        Returns:
            True if data appears to be encrypted
        """
        if not isinstance(data, str) or cls.is_fallback_plaintext(data):
            return False
        
        try:
            encrypted_bytes = base64.b64decode(data)
            # Check minimum length
            if len(encrypted_bytes) < 1 + cls.IV_SIZE + cls.TAG_SIZE:
                return False
            # Check if first byte is a valid version
            version = encrypted_bytes[0]
            return 0 <= version <= 255
        except Exception:
            return False

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new random master key.
        
        Returns:
            A new 64-character hex string (32 bytes)
        """
        return os.urandom(cls.KEY_SIZE).hex()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the derived key cache."""
        cls._key_cache.clear()
        logger.info("Encryption key cache cleared")


def encrypted_charfield(**kwargs):
    """
    Create an encrypted CharField for Django models.
    
    This is a convenience function that returns a Django CharField
    with encryption capabilities through the EncryptedFieldMixin.
    
    Example:
        class UserProfile(EncryptedFieldMixin, models.Model):
            ssn = encrypted_charfield(max_length=255)
            notes = encrypted_charfield(max_length=1000)
    """
    return EncryptedCharField(**kwargs)


def encrypted_textfield(**kwargs):
    """
    Create an encrypted TextField for Django models.
    
    This is similar to encrypted_charfield but for longer text content.
    
    Example:
        class Document(EncryptedFieldMixin, models.Model):
            content = encrypted_textfield()
            metadata = encrypted_textfield()
    """
    return EncryptedTextField(**kwargs)


def encrypted_datefield(**kwargs):
    """Create an encrypted DateField."""
    return EncryptedDateField(**kwargs)


def encrypted_jsonfield(**kwargs):
    """Create an encrypted JSONField."""
    return EncryptedJSONField(**kwargs)


class EncryptedFieldMixin:
    """
    Mixin for Django models that provides automatic encryption/decryption
    of sensitive fields.
    
    This mixin works with encrypted_charfield and encrypted_textfield
    to automatically handle encryption and decryption.
    
    Example:
        class UserProfile(EncryptedFieldMixin, models.Model):
            ssn = encrypted_charfield(max_length=255)
            notes = encrypted_textfield()
            
            class Meta:
                # Fields that should be encrypted
                encrypted_fields = ['ssn', 'notes']
    """
    
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_encrypted_fields()

    @classmethod
    def get_encrypted_field_names(cls) -> list[str]:
        """Return field names using encrypted field implementations."""
        return [
            field.name
            for field in cls._meta.fields
            if getattr(field, "is_encrypted", False)
        ]

    def _setup_encrypted_fields(self):
        """Hook for future field-specific setup."""
        return None

    def save(self, *args, **kwargs):
        """Save the model with encryption."""
        super().save(*args, **kwargs)
    
    def refresh_from_db(self, *args, **kwargs):
        """Refresh from database with decryption."""
        super().refresh_from_db(*args, **kwargs)

    def reencrypt_encrypted_fields(self, save: bool = True):
        """
        Re-save encrypted fields so values are re-encrypted with the current key version.
        """
        update_fields = self.get_encrypted_field_names()
        for field_name in update_fields:
            setattr(self, field_name, getattr(self, field_name))
        if save and update_fields:
            self.save(update_fields=update_fields)
        return update_fields


class BaseEncryptedFieldMixin:
    """Shared behavior for encrypted Django model fields."""

    is_encrypted = True

    def __init__(self, *args, encryption_context: Optional[str] = None, **kwargs):
        self.encryption_context = encryption_context
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.encryption_context:
            kwargs["encryption_context"] = self.encryption_context
        return name, path, args, kwargs

    def db_type(self, connection):
        return models.TextField().db_type(connection)

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(cls, name, private_only=private_only)
        if not self.encryption_context:
            self.encryption_context = f"{cls._meta.app_label}.{cls._meta.model_name}.{name}"

    def _serialize_plain_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _deserialize_plain_value(self, value: Any) -> Any:
        return value

    def get_prep_value(self, value):
        if isinstance(value, str) and (
            EncryptionService.is_encrypted(value)
            or EncryptionService.is_fallback_plaintext(value)
        ):
            return value
        value = super().get_prep_value(value)
        if value is None:
            return None
        serialized = self._serialize_plain_value(value)
        if serialized is None:
            return None
        return EncryptionService.encrypt(serialized, context=self.encryption_context)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        if EncryptionService.is_fallback_plaintext(value):
            return self._deserialize_plain_value(
                EncryptionService.unwrap_fallback_plaintext(value)
            )
        if EncryptionService.is_encrypted(value):
            decrypted = EncryptionService.decrypt(value, context=self.encryption_context)
            return self._deserialize_plain_value(decrypted)
        return self._deserialize_plain_value(value)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


class EncryptedCharField(BaseEncryptedFieldMixin, models.CharField):
    """CharField stored encrypted at rest."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 255)
        super().__init__(*args, **kwargs)


class EncryptedTextField(BaseEncryptedFieldMixin, models.TextField):
    """TextField stored encrypted at rest."""


class EncryptedDateField(BaseEncryptedFieldMixin, models.DateField):
    """DateField stored as encrypted text at rest."""

    def _serialize_plain_value(self, value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.isoformat()
        parsed = models.DateField.to_python(self, value)
        return parsed.isoformat() if parsed else None

    def _deserialize_plain_value(self, value: Any) -> Any:
        if value in (None, ""):
            return None
        return models.DateField.to_python(self, value)


class EncryptedJSONField(BaseEncryptedFieldMixin, models.JSONField):
    """JSONField stored as encrypted text at rest."""

    def _serialize_plain_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value)

    def _deserialize_plain_value(self, value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list, tuple, bool, int, float)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value


# Utility functions for working with encrypted data

def encrypt_model_field(instance, field_name: str, user_id: Optional[int] = None) -> str:
    """
    Encrypt a specific field value on a model instance.
    
    Args:
        instance: The Django model instance
        field_name: The name of the field to encrypt
        user_id: Optional user ID for user-specific encryption
        
    Returns:
        The encrypted value
    """
    value = getattr(instance, field_name, None)
    if value is None:
        return None
    field = instance._meta.get_field(field_name)
    context = getattr(field, "encryption_context", None)
    return EncryptionService.encrypt(str(value), user_id=user_id, context=context)


def decrypt_model_field(instance, field_name: str, user_id: Optional[int] = None) -> str:
    """
    Decrypt a specific field value on a model instance.
    
    Args:
        instance: The Django model instance
        field_name: The name of the field to decrypt
        user_id: Optional user ID for user-specific decryption
        
    Returns:
        The decrypted value
    """
    value = getattr(instance, field_name, None)
    if value is None:
        return None
    field = instance._meta.get_field(field_name)
    context = getattr(field, "encryption_context", None)
    return EncryptionService.decrypt(str(value), user_id=user_id, context=context)


def batch_encrypt(values: list, user_id: Optional[int] = None) -> list:
    """
    Encrypt a batch of values.
    
    Args:
        values: List of values to encrypt
        user_id: Optional user ID for user-specific encryption
        
    Returns:
        List of encrypted values
    """
    return [EncryptionService.encrypt(str(v), user_id=user_id) for v in values]


def batch_decrypt(values: list, user_id: Optional[int] = None) -> list:
    """
    Decrypt a batch of values.
    
    Args:
        values: List of encrypted values to decrypt
        user_id: Optional user ID for user-specific decryption
        
    Returns:
        List of decrypted values
    """
    return [EncryptionService.decrypt(str(v), user_id=user_id) for v in values]


def get_encrypted_model_fields(model_class) -> list[models.Field]:
    """Return encrypted field instances declared on a model class."""
    return [
        field for field in model_class._meta.fields
        if getattr(field, "is_encrypted", False)
    ]


def reencrypt_queryset(queryset: Iterable, batch_size: int = 100) -> int:
    """
    Re-encrypt all encrypted fields in a queryset using the currently configured key version.
    """
    updated = 0
    for instance in queryset.iterator(chunk_size=batch_size):
        field_names = [
            field.name for field in get_encrypted_model_fields(instance.__class__)
        ]
        if not field_names:
            continue
        for field_name in field_names:
            setattr(instance, field_name, getattr(instance, field_name))
        instance.save(update_fields=field_names)
        updated += 1
    return updated
