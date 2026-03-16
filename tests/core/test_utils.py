"""Tests for core utility helpers."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core import utils
from apps.resources.models import Resource


def test_generate_unique_id_is_hex_and_unique():
    first = utils.generate_unique_id()
    second = utils.generate_unique_id()

    assert first != second
    assert len(first) == 32
    int(first, 16)


def test_generate_random_string_returns_non_empty():
    value = utils.generate_random_string(16)

    assert isinstance(value, str)
    assert len(value) >= 16


def test_hash_file_uses_chunks():
    class FakeFile:
        def chunks(self):
            return [b"hello", b" ", b"world"]

    assert utils.hash_file(FakeFile()) == "5eb63bbbe01eeed093cb22bb8f5acdc3"


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("document.pdf", "pdf"),
        ("archive.TAR.GZ", "gz"),
        ("noext", ""),
        ("image.jpeg", "jpeg"),
    ],
)
def test_get_file_extension(filename, expected):
    assert utils.get_file_extension(filename) == expected


@pytest.mark.parametrize(
    "size_bytes,expected",
    [
        (512, "512.00 B"),
        (1024, "1.00 KB"),
        (1024 * 1024, "1.00 MB"),
        (1024 * 1024 * 1024, "1.00 GB"),
    ],
)
def test_format_file_size(size_bytes, expected):
    assert utils.format_file_size(size_bytes) == expected


def test_get_client_ip_prefers_x_forwarded_for():
    request = SimpleNamespace(
        META={
            "HTTP_X_FORWARDED_FOR": "10.0.0.1, 192.168.1.1",
            "REMOTE_ADDR": "127.0.0.1",
        }
    )

    assert utils.get_client_ip(request) == "10.0.0.1"


def test_get_client_ip_falls_back_to_remote_addr():
    request = SimpleNamespace(META={"REMOTE_ADDR": "127.0.0.1"})

    assert utils.get_client_ip(request) == "127.0.0.1"


def test_get_user_agent_returns_empty_string_when_missing():
    request = SimpleNamespace(META={})
    assert utils.get_user_agent(request) == ""


def test_calculate_average_rating_handles_empty_and_values():
    assert utils.calculate_average_rating([]) == 0
    assert utils.calculate_average_rating([4, 5, 3]) == 4


def test_send_email_renders_and_sends(monkeypatch):
    calls = {}

    def fake_render(template_name, context):
        calls["template"] = template_name
        calls["context"] = context
        return "<p>Hello</p>"

    def fake_send_email(
        *,
        subject,
        message,
        recipient_list,
        html_message=None,
        from_email=None,
        fail_silently=False,
    ):
        calls["mail"] = {
            "subject": subject,
            "message": message,
            "from_email": from_email,
            "recipients": recipient_list,
            "html_message": html_message,
            "fail_silently": fail_silently,
        }
        return True

    monkeypatch.setattr(utils, "render_to_string", fake_render)
    monkeypatch.setattr(
        "apps.core.emails.EmailService.send_email",
        fake_send_email,
    )

    utils.send_email(
        subject="Welcome",
        template_name="emails/welcome.html",
        context={"name": "A"},
        to_email="a@test.com",
    )

    assert calls["template"] == "emails/welcome.html"
    assert calls["context"] == {"name": "A"}
    assert calls["mail"]["subject"] == "Welcome"
    assert calls["mail"]["recipients"] == ["a@test.com"]
    assert calls["mail"]["message"] == "<p>Hello</p>"
    assert calls["mail"]["html_message"] == "<p>Hello</p>"
    assert calls["mail"]["fail_silently"] is False


def test_get_time_ago_ranges():
    now = timezone.now()

    assert utils.get_time_ago(now - timedelta(seconds=30)) == "Just now"
    assert utils.get_time_ago(now - timedelta(minutes=2)) == "2 minutes ago"
    assert utils.get_time_ago(now - timedelta(hours=3)) == "3 hours ago"
    assert utils.get_time_ago(now - timedelta(days=2)) == "2 days ago"
    assert utils.get_time_ago(now - timedelta(days=65)) == "2 months ago"
    assert utils.get_time_ago(now - timedelta(days=800)) == "2 years ago"


def test_is_valid_uuid_checks_strings():
    assert utils.is_valid_uuid(str(uuid4()))
    assert not utils.is_valid_uuid("not-a-uuid")
    assert not utils.is_valid_uuid(None)


def test_clean_html_and_truncate_text():
    assert utils.clean_html("<p>Hello <b>World</b></p>") == "Hello World"
    assert utils.truncate_text("hello", 10) == "hello"
    assert utils.truncate_text("hello world", 5, "..") == "hello.."


def test_static_choice_helpers_return_expected_values():
    resource_types = utils.get_resource_types()
    statuses = utils.get_resource_statuses()
    notification_types = utils.get_notification_types()
    roles = utils.get_user_roles()

    assert any(item["value"] == "notes" for item in resource_types)
    assert any(item["value"] == "approved" for item in statuses)
    assert any(item["value"] == "new_comment" for item in notification_types)
    assert any(item["value"] == "ADMIN" for item in roles)


@pytest.mark.django_db
def test_generate_slug_handles_conflicts_and_pk_exclusion(user):
    existing = Resource.objects.create(
        title="Existing",
        slug="test-title",
        resource_type="notes",
        uploaded_by=user,
    )

    assert utils.generate_slug("Test Title", Resource) == "test-title-1"
    assert (
        utils.generate_slug("Test Title", Resource, pk=existing.pk)
        == "test-title"
    )
