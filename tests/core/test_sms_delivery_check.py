"""Tests for sms_delivery_check management command."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@override_settings(
    SMS_PROVIDER="africas_talking",
    AFRICAS_TALKING_USERNAME="sandbox",
    AFRICAS_TALKING_API_KEY="test-key",
    AFRICAS_TALKING_SHORT_CODE="",
)
def test_sms_delivery_check_passes_when_configured():
    out = StringIO()

    call_command("sms_delivery_check", stdout=out)

    output = out.getvalue()
    assert "SMS_PROVIDER: africas_talking" in output
    assert "[OK] africastalking SMS provider is configured" in output


@override_settings(
    SMS_PROVIDER="africas_talking",
    AFRICAS_TALKING_USERNAME="",
    AFRICAS_TALKING_API_KEY="",
    AFRICAS_TALKING_SHORT_CODE="",
)
def test_sms_delivery_check_warns_when_incomplete():
    out = StringIO()

    call_command("sms_delivery_check", stdout=out)

    output = out.getvalue()
    assert "[WARN] africastalking SMS provider is missing required settings:" in output


@override_settings(
    SMS_PROVIDER="africas_talking",
    AFRICAS_TALKING_USERNAME="",
    AFRICAS_TALKING_API_KEY="",
)
def test_sms_delivery_check_strict_config_fails_when_incomplete():
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("sms_delivery_check", "--strict-config", stdout=out)


@override_settings(
    SMS_PROVIDER="africas_talking",
    AFRICAS_TALKING_USERNAME="sandbox",
    AFRICAS_TALKING_API_KEY="test-key",
)
def test_sms_delivery_check_can_send_live_test():
    out = StringIO()

    with patch(
        "apps.core.management.commands.sms_delivery_check.sms_service.send",
        return_value={"success": True},
    ) as mock_send:
        call_command(
            "sms_delivery_check",
            "--send",
            "--to",
            "+254700000001",
            stdout=out,
        )

    mock_send.assert_called_once()
    output = out.getvalue()
    assert "[OK] Test SMS sent successfully to +254700000001" in output
