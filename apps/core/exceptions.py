"""
Custom exceptions for CampusHub.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class CampusHubException(APIException):
    """Base exception for CampusHub."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred."
    default_code = "error"


class ResourceNotFoundError(CampusHubException):
    """Exception for resource not found."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found."
    default_code = "not_found"


class ResourceAlreadyExistsError(CampusHubException):
    """Exception for duplicate resource."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource already exists."
    default_code = "already_exists"


class UnauthorizedError(CampusHubException):
    """Exception for unauthorized access."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication credentials were not provided."
    default_code = "unauthorized"


class ForbiddenError(CampusHubException):
    """Exception for forbidden access."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "forbidden"


class ValidationError(CampusHubException):
    """Exception for validation errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid data provided."
    default_code = "validation_error"


class FileSizeError(CampusHubException):
    """Exception for file size errors."""

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "File size exceeds the maximum allowed size."
    default_code = "file_size_error"


class FileTypeError(CampusHubException):
    """Exception for file type errors."""

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "File type not supported."
    default_code = "file_type_error"


class RateLimitExceededError(CampusHubException):
    """Exception for rate limit errors."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded. Please try again later."
    default_code = "rate_limit_exceeded"


class ModerationError(CampusHubException):
    """Exception for moderation errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Moderation action failed."
    default_code = "moderation_error"


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "status_code": response.status_code,
            "message": response.data.get("detail", str(exc)),
            "code": getattr(exc, "default_code", "error"),
        }

        # Add field errors if available
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            response.data["errors"] = exc.detail

    return response
