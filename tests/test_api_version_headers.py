import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware.api_version_headers import APIVersionHeadersMiddleware


@pytest.mark.parametrize(
    "path,expected_version,deprecated",
    [
        ("/api/v1/resources/", "v1", "false"),
        ("/api/v2/status/", "v2", "false"),
        ("/api/resources/", "legacy", "true"),
    ],
)
def test_api_version_headers(path, expected_version, deprecated):
    rf = RequestFactory()
    request = rf.get(path)
    response = HttpResponse()

    middleware = APIVersionHeadersMiddleware(lambda req: response)
    result = middleware.process_response(request, response)

    assert result["X-API-Version"] == expected_version
    assert result["Deprecation"] == deprecated
