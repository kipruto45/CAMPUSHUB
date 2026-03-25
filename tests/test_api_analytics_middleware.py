import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.api.middleware import APIAnalyticsMiddleware


@pytest.mark.django_db
def test_api_analytics_middleware_creates_event(settings):
    settings.ANALYTICS_HMAC_SECRET = "secret123"
    rf = RequestFactory()
    ts = int(timezone.now().timestamp())
    path = "/api/v1/ping/"

    import hmac, hashlib

    sig = hmac.new(
        settings.ANALYTICS_HMAC_SECRET.encode(),
        f"GET:{path}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()

    request = rf.get(
        path,
        HTTP_X_SESSION_ID="sess123",
        HTTP_X_ANALYTICS_SIGNATURE=sig,
        HTTP_X_ANALYTICS_TIMESTAMP=str(ts),
    )
    response = HttpResponse(status=200)

    # Process response
    middleware = APIAnalyticsMiddleware(lambda req: response)
    result = middleware.process_response(request, response)

    assert result.status_code == 200

    # Event should be created
    from apps.analytics.models import AnalyticsEvent

    event = AnalyticsEvent.objects.latest("timestamp")
    assert event.event_type == "api_request"
    assert event.session_id == "sess123"


@pytest.mark.django_db
def test_api_analytics_middleware_skips_on_bad_signature(settings):
    settings.ANALYTICS_HMAC_SECRET = "secret123"
    rf = RequestFactory()
    request = rf.get(
        "/api/v1/ping/",
        HTTP_X_SESSION_ID="sess123",
        HTTP_X_ANALYTICS_SIGNATURE="bad",
        HTTP_X_ANALYTICS_TIMESTAMP="123",
    )
    response = HttpResponse(status=200)

    middleware = APIAnalyticsMiddleware(lambda req: response)
    middleware.process_response(request, response)

    from apps.analytics.models import AnalyticsEvent

    assert AnalyticsEvent.objects.count() == 0
