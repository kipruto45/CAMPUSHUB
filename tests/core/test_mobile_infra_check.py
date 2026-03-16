"""Tests for mobile infrastructure backend readiness command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

# Minimal URLConf used to assert missing mobile-route failures.
urlpatterns = []


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="testing",
    FCM_ENABLED=False,
    APNS_ENABLED=False,
)
def test_mobile_infra_check_passes_in_testing_mode():
    out = StringIO()

    call_command("mobile_infra_check", stdout=out)

    output = out.getvalue()
    assert "Mobile infra check summary: failures=0" in output
    assert "[OK] database" in output
    assert "[OK] mobile_urls" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="testing",
    FCM_ENABLED=True,
    FCM_SERVER_KEY="",
    FCM_PROJECT_ID="",
    APNS_ENABLED=False,
)
def test_mobile_infra_check_strict_push_fails_when_provider_misconfigured():
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("mobile_infra_check", "--strict-push", stdout=out)

    output = out.getvalue()
    assert "[FAIL] push_fcm" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="testing",
    ROOT_URLCONF="tests.core.test_mobile_infra_check",
    FCM_ENABLED=False,
    APNS_ENABLED=False,
)
def test_mobile_infra_check_fails_when_mobile_urls_are_missing():
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("mobile_infra_check", stdout=out)

    output = out.getvalue()
    assert "[FAIL] mobile_urls" in output


@pytest.mark.django_db
@override_settings(
    ENVIRONMENT="development",
    REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": {}},
    FCM_ENABLED=False,
    APNS_ENABLED=False,
)
def test_mobile_infra_check_requires_mobile_throttle_rates_outside_testing():
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("mobile_infra_check", stdout=out)

    output = out.getvalue()
    assert "[FAIL] mobile_throttle_rates" in output
