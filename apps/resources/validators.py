"""Validation utilities for resource uploads."""

import mimetypes
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_UPLOAD_EXTENSIONS = {
    # Documents
    "pdf", "docx", "pptx", "txt", "zip", "doc", "xlsx", "xls", "csv",
    # Images
    "jpg", "jpeg", "png", "gif", "webp", "bmp",
    # Videos
    "mp4", "mpeg", "mpg", "mov", "avi", "webm", "mkv",
    # Audio/Recordings
    "mp3", "wav", "ogg", "webm", "aac", "m4a", "flac",
}
ALLOWED_UPLOAD_MIME_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
    "text/plain",
    "application/zip",
    "application/x-zip-compressed",
    "text/csv",
    "application/csv",
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Videos
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
    # Audio/Recordings
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/aac",
    "audio/x-m4a",
}
MAX_UPLOAD_SIZE = getattr(settings, "MAX_FILE_SIZE", 50 * 1024 * 1024)
try:
    MAX_UPLOAD_SIZE = int(MAX_UPLOAD_SIZE)
except (TypeError, ValueError):
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """Return a safe normalized filename for storage/comparison."""
    name = Path(filename).name
    name = name.replace(" ", "_")
    # Keep only alnum, dot, underscore, hyphen.
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name.lower()


def detect_extension(uploaded_file) -> str:
    """Get lowercase extension without dot."""
    _, ext = os.path.splitext(uploaded_file.name)
    return ext.lower().lstrip(".")


def validate_upload_file(uploaded_file) -> dict:
    """Validate file extension, mime and size."""
    if not uploaded_file:
        raise ValidationError("File is required.")

    extension = detect_extension(uploaded_file)
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}."
        )

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            f"File is too large. Maximum allowed is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."
        )

    mime_type = (
        getattr(uploaded_file, "content_type", None)
        or mimetypes.guess_type(uploaded_file.name)[0]
    )
    if mime_type and mime_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise ValidationError(f"Unsupported MIME type '{mime_type}'.")

    return {
        "extension": extension,
        "mime_type": mime_type or "",
        "size": uploaded_file.size,
        "normalized_filename": sanitize_filename(uploaded_file.name),
    }


def normalize_title(title: str) -> str:
    """Trim and collapse excessive spaces."""
    return re.sub(r"\s+", " ", (title or "").strip())


def normalize_tags(tags: str) -> str:
    """Normalize comma-separated tags and deduplicate while preserving order."""
    if not tags:
        return ""
    seen = set()
    cleaned = []
    for raw in tags.split(","):
        tag = re.sub(r"\s+", " ", raw.strip().lower())
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    return ", ".join(cleaned)


def validate_academic_relationships(
    *, faculty=None, department=None, course=None, unit=None
):
    """Ensure faculty->department->course->unit hierarchy is valid."""
    if department and faculty and department.faculty_id != faculty.id:
        raise ValidationError(
            {"department": "Department does not belong to selected faculty."}
        )

    if course and department and course.department_id != department.id:
        raise ValidationError(
            {"course": "Course does not belong to selected department."}
        )

    if unit and course and unit.course_id != course.id:
        raise ValidationError({"unit": "Unit does not belong to selected course."})


def validate_duplicate_upload(
    *,
    user,
    title: str,
    normalized_filename: str,
    file_size: int,
    exclude_resource_id=None,
):
    """Raise error for probable duplicate uploads by same user."""
    from apps.resources.models import Resource

    queryset = Resource.objects.filter(
        uploaded_by=user,
        title__iexact=title,
        normalized_filename=normalized_filename,
        file_size=file_size,
    )
    if exclude_resource_id:
        queryset = queryset.exclude(id=exclude_resource_id)

    if queryset.exists():
        raise ValidationError("A similar file has already been uploaded by you.")
