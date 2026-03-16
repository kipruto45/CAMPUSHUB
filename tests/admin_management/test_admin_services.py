"""Tests for admin management service-layer functions."""

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.admin_management import services
from apps.announcements.models import Announcement, AnnouncementStatus
from apps.comments.models import Comment
from apps.courses.models import Course, Unit
from apps.downloads.models import Download
from apps.faculties.models import Department, Faculty
from apps.moderation.models import AdminActivityLog
from apps.reports.models import Report
from apps.resources.models import Resource


def _create_resource(owner, course, **overrides):
    defaults = {
        "title": "Service Test Resource",
        "resource_type": "notes",
        "uploaded_by": owner,
        "course": course,
        "status": "pending",
        "is_public": True,
    }
    defaults.update(overrides)
    return Resource.objects.create(**defaults)


@pytest.mark.django_db
def test_user_display_name_helper(user):
    user.first_name = ""
    user.last_name = ""
    user.full_name = "Display Name"
    assert services._user_display_name(user) == "Display Name"

    user.full_name = ""
    assert services._user_display_name(user) == user.email


@pytest.mark.django_db
def test_stats_services_return_expected_shapes(user, admin_user):
    faculty = Faculty.objects.create(name="Engineering", code="ENGX")
    department = Department.objects.create(
        faculty=faculty,
        name="Software",
        code="SOFX",
    )
    course = Course.objects.create(
        department=department,
        name="BSc Software",
        code="BSCX",
        duration_years=4,
    )
    Unit.objects.create(
        course=course,
        name="Algorithms",
        code="CS401",
        semester="1",
        year_of_study=4,
    )
    resource = _create_resource(
        admin_user,
        course,
        title="Approved Resource",
        status="approved",
    )
    Download.objects.create(user=user, resource=resource)
    report = Report.objects.create(
        reporter=user,
        resource=resource,
        reason_type="spam",
        message="Looks like spam",
        status="open",
    )
    Comment.objects.create(user=user, resource=resource, content="Needs review")

    dashboard = services.get_admin_dashboard_data()
    user_stats = services.get_user_management_stats()
    resource_stats = services.get_resource_management_stats()
    academic_stats = services.get_academic_stats()
    queue = services.get_moderation_queues()

    assert dashboard["users"]["total"] >= 2
    assert dashboard["resources"]["total"] >= 1
    assert dashboard["reports"]["total"] >= 1
    assert (
        dashboard["reports"]["open"] + dashboard["reports"]["in_review"]
    ) >= 1
    assert dashboard["engagement"]["downloads"] >= 1
    assert dashboard["recent_reports"][0]["id"] == str(report.id)
    assert user_stats["total"] >= 2
    assert isinstance(resource_stats["by_status"], list)
    assert isinstance(resource_stats["by_type"], list)
    assert academic_stats["faculties"] >= 1
    assert (queue["open_reports"] + queue["in_review_reports"]) >= 1


@pytest.mark.django_db
def test_update_user_status_guardrails(user, admin_user):
    same_actor = services.update_user_status(actor=user, target=user, is_active=False)
    assert same_actor["success"] is False

    super_target = services.update_user_status(
        actor=user,
        target=admin_user,
        is_active=False,
    )
    assert super_target["success"] is False

    already_active = services.update_user_status(
        actor=admin_user,
        target=user,
        is_active=True,
    )
    assert already_active["success"] is True
    assert "already active" in already_active["message"]

    deactivated = services.update_user_status(
        actor=admin_user,
        target=user,
        is_active=False,
    )
    user.refresh_from_db()
    assert deactivated["success"] is True
    assert user.is_active is False
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="user_suspended",
        target_type="user",
        target_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_update_user_role_rules(user, admin_user):
    blocked = services.update_user_role(
        actor=user,
        target=admin_user,
        role="MODERATOR",
    )
    assert blocked["success"] is False

    unchanged = services.update_user_role(
        actor=admin_user,
        target=user,
        role="STUDENT",
    )
    assert unchanged["success"] is True
    assert "already has role" in unchanged["message"]

    changed = services.update_user_role(
        actor=admin_user,
        target=user,
        role="moderator",
    )
    user.refresh_from_db()
    assert changed["success"] is True
    assert user.role == "MODERATOR"
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="user_role_updated",
        target_type="user",
        target_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_review_resource_dispatches_to_moderation_service(user, admin_user):
    faculty = Faculty.objects.create(name="Science", code="SCIX")
    department = Department.objects.create(
        faculty=faculty,
        name="Computer Science",
        code="CSX",
    )
    course = Course.objects.create(
        department=department,
        name="BSc Computer Science",
        code="BSCX",
        duration_years=4,
    )
    resource = _create_resource(user, course, title="Pending moderation target")

    with patch(
        "apps.admin_management.services.ModerationService.approve_resource",
        return_value={"ok": True},
    ) as approve_mock:
        result = services.review_resource(
            resource=resource,
            reviewer=admin_user,
            approve=True,
            reason="Looks good",
        )
    approve_mock.assert_called_once()
    assert result["ok"] is True

    with patch(
        "apps.admin_management.services.ModerationService.reject_resource",
        return_value={"ok": False},
    ) as reject_mock:
        result = services.review_resource(
            resource=resource,
            reviewer=admin_user,
            approve=False,
            reason="Invalid content",
        )
    reject_mock.assert_called_once()
    assert result["ok"] is False


@pytest.mark.django_db
def test_delete_resource_and_user_manage_checks(user, admin_user):
    faculty = Faculty.objects.create(name="Humanities", code="HUMX")
    department = Department.objects.create(
        faculty=faculty,
        name="History",
        code="HISX",
    )
    course = Course.objects.create(
        department=department,
        name="BA History",
        code="HISTX",
        duration_years=3,
    )
    upload = SimpleUploadedFile(
        "sample.pdf",
        b"pdf-bytes",
        content_type="application/pdf",
    )
    resource = _create_resource(
        admin_user,
        course,
        title="Delete Candidate",
        status="approved",
        file=upload,
    )
    resource_id = resource.id
    result = services.delete_resource(resource=resource, actor=admin_user)

    assert result["success"] is True
    assert not Resource.objects.filter(id=resource_id).exists()
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="resource_deleted",
        target_type="resource",
        target_id=str(resource_id),
    ).exists()
    assert services.can_manage_target_user(actor=admin_user, target=user) is True
    assert services.can_manage_target_user(actor=user, target=admin_user) is False


@pytest.mark.django_db
def test_update_report_status_triggers_notifications_and_release_hooks(
    user,
    admin_user,
):
    faculty = Faculty.objects.create(name="Law", code="LWX")
    department = Department.objects.create(
        faculty=faculty,
        name="Jurisprudence",
        code="JURX",
    )
    course = Course.objects.create(
        department=department,
        name="LLB",
        code="LLBX",
        duration_years=4,
    )
    resource = _create_resource(admin_user, course, status="approved")
    comment = Comment.objects.create(user=admin_user, resource=resource, content="Text")
    report = Report.objects.create(
        reporter=user,
        comment=comment,
        reason_type="abusive",
        message="Abusive language",
        status="open",
    )

    with patch(
        "apps.admin_management.services.NotificationService.notify_report_status"
    ) as notify_mock:
        with patch(
            "apps.admin_management.services."
            "ModerationService.maybe_release_comment_after_report_decision"
        ) as release_mock:
            updated = services.update_report_status(
                report=report,
                reviewer=admin_user,
                status="resolved",
                resolution_note="Handled",
            )

    report.refresh_from_db()
    assert updated.id == report.id
    assert report.status == "resolved"
    assert report.reviewed_by_id == admin_user.id
    notify_mock.assert_called_once_with(report)
    release_mock.assert_called_once_with(report)
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="report_resolved",
        target_type="report",
        target_id=str(report.id),
    ).exists()


@pytest.mark.django_db
def test_announcement_lifecycle_actions(admin_user):
    announcement = Announcement.objects.create(
        title="System Maintenance",
        content="Downtime window",
        created_by=admin_user,
    )

    published = services.announcement_lifecycle_action(
        announcement=announcement,
        action="publish",
        actor=admin_user,
    )
    assert published.status == AnnouncementStatus.PUBLISHED
    assert published.published_at is not None
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="announcement_published",
        target_type="announcement",
        target_id=str(announcement.id),
    ).exists()

    archived = services.announcement_lifecycle_action(
        announcement=announcement,
        action="archive",
        actor=admin_user,
    )
    assert archived.status == AnnouncementStatus.ARCHIVED
    assert AdminActivityLog.objects.filter(
        admin=admin_user,
        action="announcement_archived",
        target_type="announcement",
        target_id=str(announcement.id),
    ).exists()

    unpublished = services.announcement_lifecycle_action(
        announcement=announcement,
        action="unpublish",
        actor=admin_user,
    )
    assert unpublished.status == AnnouncementStatus.DRAFT
    assert unpublished.published_at is None

    untouched = services.announcement_lifecycle_action(
        announcement=announcement,
        action="noop",
    )
    assert untouched.updated_at <= timezone.now()
