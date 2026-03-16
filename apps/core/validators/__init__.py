"""
Core Validators for CampusHub.

This module provides:
- Unified validation system
- Common validators
- Validator classes
"""

from apps.core.validators.unified import (
    # Classes
    ValidationResult,
    ValidationRule,
    Validator,
    # User validators
    UserValidator,
    # Resource validators
    ResourceValidator,
    # File validators
    FileValidator,
    # Common validators
    validate_not_empty,
    validate_email,
    validate_phone,
    validate_registration_number,
    validate_password_strength,
    validate_url,
    validate_slug,
    validate_min_length,
    validate_max_length,
    validate_range,
    validate_choice,
    validate_file_extension,
    validate_file_size,
    validate_unique_together,
    raise_validation_error,
    # Also re-export old validators for compatibility
    validate_file_extension as old_validate_file_extension,
    validate_file_size as old_validate_file_size,
    validate_mime_type,
    validate_image_extension,
    validate_document_extension,
)

# Import old validators for backwards compatibility
from apps.core.validators import (
    validate_file_extension as old_validate_file_extension,
    validate_file_size as old_validate_file_size,
    validate_mime_type,
    validate_image_extension,
    validate_document_extension,
    validate_phone_number,
    validate_registration_number as old_validate_registration_number,
)

__all__ = [
    # Classes
    "ValidationResult",
    "ValidationRule",
    "Validator",
    # User validators
    "UserValidator",
    # Resource validators
    "ResourceValidator",
    # File validators
    "FileValidator",
    # Common validators
    "validate_not_empty",
    "validate_email",
    "validate_phone",
    "validate_registration_number",
    "validate_password_strength",
    "validate_url",
    "validate_slug",
    "validate_min_length",
    "validate_max_length",
    "validate_range",
    "validate_choice",
    "validate_file_extension",
    "validate_file_size",
    "validate_unique_together",
    "raise_validation_error",
    # Old validators (backwards compatibility)
    "validate_file_extension as old_validate_file_extension",
    "validate_file_size as old_validate_file_size",
    "validate_mime_type",
    "validate_image_extension",
    "validate_document_extension",
    "validate_phone_number",
    "validate_registration_number as old_validate_registration_number",
]
