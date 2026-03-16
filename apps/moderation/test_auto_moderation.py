import pytest

from apps.accounts.models import User
from apps.courses.models import Course
from apps.faculties.models import Department, Faculty
from apps.reports.models import Report
from apps.resources.models import Resource


@pytest.mark.django_db
def test_severe_resource_report_auto_hides_resource(monkeypatch):
    monkeypatch.setattr(
        "apps.notifications.websocket.WebSocketNotificationService.send_global_notification",
        lambda *args, **kwargs: None,
    )

    faculty = Faculty.objects.create(name="School of Computing", code="SOC")
    department = Department.objects.create(
        faculty=faculty,
        name="Computer Science",
        code="CS",
    )
    course = Course.objects.create(
        department=department,
        name="Bachelor of Science in Computer Science",
        code="BCS",
    )
    uploader = User.objects.create_user(
        email="uploader-auto-mod@example.com",
        password="testpass123",
        full_name="Uploader",
        role="student",
        faculty=faculty,
        department=department,
        course=course,
    )
    reporter = User.objects.create_user(
        email="reporter-auto-mod@example.com",
        password="testpass123",
        full_name="Reporter",
        role="student",
        faculty=faculty,
        department=department,
        course=course,
    )
    resource = Resource.objects.create(
        title="Auto Moderated Resource",
        uploaded_by=uploader,
        faculty=faculty,
        department=department,
        course=course,
        status="approved",
        is_public=True,
    )

    report = Report.objects.create(
        reporter=reporter,
        resource=resource,
        reason_type="spam",
        message="This should be hidden automatically.",
    )

    resource.refresh_from_db()
    report.refresh_from_db()

    assert resource.status == "flagged"
    assert resource.is_public is False
    assert report.status == "in_review"
