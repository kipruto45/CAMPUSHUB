"""
Unified Validators for CampusHub.

Provides centralized validation with proper error handling.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from django.core.exceptions import ValidationError


@dataclass
class ValidationRule:
    """Single validation rule."""
    field: str
    validator: Callable[[Any], bool]
    message: str
    code: str = "invalid"


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: dict[str, list[str]] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str):
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)
    
    @property
    def has_errors(self) -> bool:
        return bool(self.errors)
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
        }


class Validator:
    """
    Base validator class.
    
    Usage:
        class UserValidator(Validator):
            rules = [
                ValidationRule("email", validate_email, "Invalid email"),
            ]
    """
    
    rules: list[ValidationRule] = []
    
    def __init__(self, data: dict):
        self.data = data
        self._errors: dict[str, list[str]] = {}
    
    def validate(self) -> ValidationResult:
        """Run all validation rules."""
        result = ValidationResult(is_valid=True)
        
        for rule in self.rules:
            value = self.data.get(rule.field)
            
            try:
                if not rule.validator(value):
                    result.add_error(rule.field, rule.message)
            except Exception as e:
                result.add_error(rule.field, str(e))
        
        result.is_valid = not result.has_errors
        return result
    
    def add_error(self, field: str, message: str):
        """Add custom error."""
        if field not in self._errors:
            self._errors[field] = []
        self._errors[field].append(message)
    
    @property
    def errors(self) -> dict[str, list[str]]:
        return self._errors
    
    def is_valid(self) -> bool:
        """Quick validation check."""
        return not self._errors


# Common validators
def validate_not_empty(value: Any) -> bool:
    """Check if value is not empty."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return False
    return True


def validate_email(value: str) -> bool:
    """Validate email format."""
    if not value:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, str(value)))


def validate_phone(value: str) -> bool:
    """Validate phone number (Kenyan format)."""
    if not value:
        return False
    pattern = r'^\+?254\d{9}$|^07\d{8}$'
    return bool(re.match(pattern, str(value)))


def validate_registration_number(value: str) -> bool:
    """Validate student registration number."""
    if not value:
        return False
    pattern = r'^[A-Z]{3,4}/\d{4}/\d{3,6}$|^\d{4}/[A-Z]{3,4}/\d{3,6}$'
    return bool(re.match(pattern, str(value)))


def validate_min_length(min_length: int) -> Callable[[str], bool]:
    """Create min length validator."""
    def validator(value: str) -> bool:
        return len(str(value)) >= min_length if value else False
    return validator


def validate_max_length(max_length: int) -> Callable[[str], bool]:
    """Create max length validator."""
    def validator(value: str) -> bool:
        return len(str(value)) <= max_length if value else True
    return validator


def validate_range(min_val: float, max_val: float) -> Callable[[float], bool]:
    """Create range validator."""
    def validator(value: float) -> bool:
        try:
            return min_val <= float(value) <= max_val
        except (TypeError, ValueError):
            return False
    return validator


def validate_choice(choices: list) -> Callable[[Any], bool]:
    """Create choice validator."""
    def validator(value: Any) -> bool:
        return value in choices
    return validator


def validate_file_extension(allowed_extensions: list[str]) -> Callable[[str], bool]:
    """Create file extension validator."""
    def validator(value: str) -> bool:
        if not value:
            return True
        ext = os.path.splitext(value)[1].lower().strip(".")
        return ext in [e.lower().strip(".") for e in allowed_extensions]
    return validator


def validate_file_size(max_size: int) -> Callable[[int], bool]:
    """Create file size validator."""
    def validator(value: int) -> bool:
        try:
            return 0 <= int(value) <= max_size
        except (TypeError, ValueError):
            return False
    return validator


def validate_password_strength(value: str) -> bool:
    """Validate password strength."""
    if not value:
        return False
    if len(value) < 8:
        return False
    if not re.search(r"[A-Z]", value):
        return False
    if not re.search(r"[a-z]", value):
        return False
    if not re.search(r"\d", value):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        return False
    return True


def validate_url(value: str) -> bool:
    """Validate URL format."""
    if not value:
        return False
    pattern = r'^https?://'
    return bool(re.match(pattern, str(value)))


def validate_slug(value: str) -> bool:
    """Validate slug format."""
    if not value:
        return False
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, str(value)))


# Specific validators
class UserValidator(Validator):
    """Validator for user data."""
    
    def __init__(self, data: dict):
        super().__init__(data)
        self.rules = [
            ValidationRule(
                "email",
                validate_email,
                "Invalid email format",
                "invalid_email"
            ),
            ValidationRule(
                "password",
                validate_password_strength,
                "Password must be at least 8 characters with uppercase, lowercase, digit, and special character",
                "weak_password"
            ),
            ValidationRule(
                "registration_number",
                validate_registration_number,
                "Invalid registration number format (e.g., REG/2020/001)",
                "invalid_registration"
            ),
            ValidationRule(
                "phone_number",
                validate_phone,
                "Invalid phone number format (e.g., +254712345678)",
                "invalid_phone"
            ),
        ]


class ResourceValidator(Validator):
    """Validator for resource data."""
    
    def __init__(self, data: dict):
        super().__init__(data)
        self.rules = [
            ValidationRule(
                "title",
                validate_not_empty,
                "Title is required",
                "required"
            ),
            ValidationRule(
                "title",
                validate_max_length(500),
                "Title must be at most 500 characters",
                "max_length"
            ),
        ]


class FileValidator(Validator):
    """Validator for file uploads."""
    
    ALLOWED_EXTENSIONS = [
        "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
        "txt", "zip", "rar", "jpg", "jpeg", "png", "gif", "webp", "csv"
    ]
    
    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "application/zip",
        "application/x-zip-compressed",
        "application/x-rar-compressed",
        "application/vnd.rar",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "text/csv",
        "application/csv",
    ]
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    def __init__(self, data: dict):
        super().__init__(data)
        self.rules = [
            ValidationRule(
                "file",
                validate_not_empty,
                "File is required",
                "required"
            ),
            ValidationRule(
                "file",
                validate_file_extension(self.ALLOWED_EXTENSIONS),
                f"File type not allowed. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
                "invalid_extension"
            ),
            ValidationRule(
                "size",
                validate_file_size(self.MAX_FILE_SIZE),
                f"File size exceeds {self.MAX_FILE_SIZE / (1024*1024)}MB limit",
                "file_too_large"
            ),
        ]


def validate_model_instance(model_class, value: Any) -> bool:
    """Validate that value is an instance of model."""
    if value is None:
        return True
    return isinstance(value, model_class)


def validate_unique_together(model_class, fields: list[str]) -> Callable[[dict], bool]:
    """Create unique together validator."""
    def validator(data: dict) -> bool:
        if not data:
            return True
        filter_kwargs = {f: data.get(f) for f in fields if data.get(f)}
        if not filter_kwargs:
            return True
        return not model_class.objects.filter(**filter_kwargs).exists()
    return validator


# Django ValidationError compatibility
def raise_validation_error(message: str, code: str = None):
    """Raise Django ValidationError."""
    raise ValidationError(message, code=code)
