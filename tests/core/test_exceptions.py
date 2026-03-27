from types import SimpleNamespace

from rest_framework import status
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import custom_exception_handler


def test_custom_exception_handler_summarizes_validation_errors():
    exc = ValidationError({"email": ["This field is required."]})

    response = custom_exception_handler(exc, {"view": None, "request": None})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["status_code"] == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == "Please correct the highlighted fields and try again."
    assert response.data["code"] == "invalid"
    assert response.data["errors"] == {"email": ["This field is required."]}


def test_custom_exception_handler_hides_unhandled_exception_details():
    exc = RuntimeError("database connection refused")
    request = SimpleNamespace(path="/api/test-error/")

    response = custom_exception_handler(exc, {"view": None, "request": request})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data == {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "Something went wrong on our side. Please try again later.",
        "code": "server_error",
    }
