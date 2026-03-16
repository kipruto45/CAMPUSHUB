"""
Validators for CampusHub.
"""

import mimetypes
import os

try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    magic = None
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_extension(value):
    """
    Validate file extension against allowed extensions.
    """
    allowed_extensions = getattr(
        settings,
        "ALLOWED_FILE_EXTENSIONS",
        [
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "txt",
            "zip",
            "rar",
            "jpg",
            "jpeg",
            "png",
            "gif",
        ],
    )
    ext = os.path.splitext(value.name)[1].lower().strip(".")
    if ext not in allowed_extensions:
        raise ValidationError(
            f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}'
        )


def validate_file_size(value):
    """
    Validate file size against maximum allowed size.
    """
    max_size = getattr(settings, "MAX_FILE_SIZE", 52428800)  # 50MB default
    if value.size > max_size:
        raise ValidationError(f"File size cannot exceed {max_size / (1024 * 1024)}MB")


def validate_mime_type(value):
    """
    Validate file MIME type.
    """
    allowed_mime_types = [
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
    ]

    # Read the first 2048 bytes to detect MIME type
    file_content = value.read(2048)
    value.seek(0)  # Reset file pointer

    if magic is not None:
        mime_type = magic.from_buffer(file_content, mime=True)
    else:
        mime_type, _ = mimetypes.guess_type(value.name)

    if not mime_type or mime_type not in allowed_mime_types:
        raise ValidationError(f'File type "{mime_type}" is not allowed.')


def validate_image_extension(value):
    """
    Validate image file extension.
    """
    allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
    ext = os.path.splitext(value.name)[1].lower().strip(".")
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Image type not allowed. Allowed types: {", ".join(allowed_extensions)}'
        )


def validate_document_extension(value):
    """
    Validate document file extension.
    """
    allowed_extensions = ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt"]
    ext = os.path.splitext(value.name)[1].lower().strip(".")
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Document type not allowed. Allowed types: {", ".join(allowed_extensions)}'
        )


def validate_registration_number(value):
    """
    Validate student registration number format.
    """
    import re

    # Example format: REG/2020/001 or 2020/REG/001
    pattern = r"^[A-Z]{3,4}/\d{4}/\d{3,6}$|^\d{4}/[A-Z]{3,4}/\d{3,6}$"
    if not re.match(pattern, value):
        raise ValidationError(
            "Invalid registration number format. Expected format: REG/2020/001 or 2020/REG/001"
        )


def validate_phone_number(value):
    """
    Validate phone number format.
    """
    import re

    # Example format: +254712345678 or 0712345678
    pattern = r"^\+?254\d{9}$|^07\d{8}$"
    if not re.match(pattern, value):
        raise ValidationError(
            "Invalid phone number format. Expected format: +254712345678 or 0712345678"
        )


def validate_password_strength(value):
    """
    Validate password strength.
    """
    import re

    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")

    if not re.search(r"[A-Z]", value):
        raise ValidationError("Password must contain at least one uppercase letter.")

    if not re.search(r"[a-z]", value):
        raise ValidationError("Password must contain at least one lowercase letter.")

    if not re.search(r"\d", value):
        raise ValidationError("Password must contain at least one digit.")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        raise ValidationError("Password must contain at least one special character.")
