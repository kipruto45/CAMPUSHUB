"""
Custom exceptions and safe error helpers for CampusHub.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


DEFAULT_PUBLIC_ERROR_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "We couldn't process that request.",
    status.HTTP_401_UNAUTHORIZED: "Authentication is required to continue.",
    status.HTTP_403_FORBIDDEN: "You do not have permission to perform this action.",
    status.HTTP_404_NOT_FOUND: "The requested resource was not found.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "This action is not allowed.",
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "The uploaded file is too large.",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "This file or media type is not supported.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests. Please try again later.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "Something went wrong on our side. Please try again later."
    ),
}

VALIDATION_SUMMARY_MESSAGE = "Please correct the highlighted fields and try again."


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


def _serialize_error_detail(detail):
    if isinstance(detail, ErrorDetail):
        return str(detail)
    if isinstance(detail, dict):
        return {key: _serialize_error_detail(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_serialize_error_detail(item) for item in detail]
    if isinstance(detail, tuple):
        return [_serialize_error_detail(item) for item in detail]
    return detail


def _default_public_message(status_code: int) -> str:
    return DEFAULT_PUBLIC_ERROR_MESSAGES.get(
        status_code,
        DEFAULT_PUBLIC_ERROR_MESSAGES[status.HTTP_500_INTERNAL_SERVER_ERROR],
    )


def _public_message_from_detail(status_code: int, detail) -> str:
    if status_code >= 500:
        return _default_public_message(status.HTTP_500_INTERNAL_SERVER_ERROR)
    if isinstance(detail, (ErrorDetail, str)):
        text = str(detail).strip()
        return text or _default_public_message(status_code)
    if isinstance(detail, (dict, list, tuple)):
        if status_code == status.HTTP_400_BAD_REQUEST:
            return VALIDATION_SUMMARY_MESSAGE
        return _default_public_message(status_code)
    return _default_public_message(status_code)


def _error_code_for_exception(exc) -> str:
    if hasattr(exc, "get_codes"):
        code = exc.get_codes()
        if isinstance(code, str):
            return code
    return getattr(exc, "default_code", "error")


def safe_error_response(
    *,
    message: str,
    status_code: int,
    field: str = "detail",
    extra: dict | None = None,
):
    payload = {field: message}
    if extra:
        payload.update(extra)
    return Response(payload, status=status_code)


def log_exception_response(
    *,
    logger_obj,
    log_message: str,
    user_message: str,
    status_code: int,
    field: str = "detail",
    extra: dict | None = None,
):
    (logger_obj or logger).exception(log_message)
    return safe_error_response(
        message=user_message,
        status_code=status_code,
        field=field,
        extra=extra,
    )


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    response = exception_handler(exc, context)

    if response is None:
        view = context.get("view")
        request = context.get("request")
        logger.exception(
            "Unhandled API exception in view=%s path=%s",
            view.__class__.__name__ if view is not None else "unknown",
            getattr(request, "path", "unknown"),
        )
        return Response(
            {
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": _default_public_message(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                "code": "server_error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = getattr(exc, "detail", response.data)
    serialized_detail = _serialize_error_detail(detail)
    payload = {
        "status_code": response.status_code,
        "message": _public_message_from_detail(response.status_code, detail),
        "code": _error_code_for_exception(exc),
    }

    if isinstance(serialized_detail, (dict, list)):
        payload["errors"] = serialized_detail

    response.data = payload
    return response
