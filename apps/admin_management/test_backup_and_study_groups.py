import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.courses.models import Course
from apps.faculties.models import Department, Faculty
from apps.social.models import StudyGroup, StudyGroupMember


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-tools@example.com",
        password="testpass123",
        full_name="Admin Tools",
        role="ADMIN",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def study_group_course(db):
    faculty = Faculty.objects.create(name="School of Computing", code="SOC")
    department = Department.objects.create(
        faculty=faculty,
        name="Computer Science",
        code="CS",
    )
    course = Course.objects.create(
        department=department,
        name="Bachelor of Science in Computer Science",
        code="BCSC",
    )
    return faculty, department, course


@pytest.mark.django_db
def test_admin_study_group_list_includes_private_groups(admin_client, study_group_course):
    faculty, department, course = study_group_course
    creator = User.objects.create_user(
        email="group-owner@example.com",
        password="testpass123",
        full_name="Group Owner",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )

    private_group = StudyGroup.objects.create(
        name="Private Revision Group",
        description="Invite-only discussion room",
        creator=creator,
        course=course,
        faculty=faculty,
        department=department,
        is_public=False,
        privacy="private",
    )

    response = admin_client.get(reverse("admin_management:study-group-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(private_group.id)
    assert response.data["results"][0]["is_public"] is False
    assert response.data["results"][0]["privacy"] == "private"


@pytest.mark.django_db
def test_admin_study_group_list_returns_active_member_count(
    admin_client, study_group_course
):
    faculty, department, course = study_group_course
    creator = User.objects.create_user(
        email="member-count-owner@example.com",
        password="testpass123",
        full_name="Member Count Owner",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )
    active_member = User.objects.create_user(
        email="member-count-active@example.com",
        password="testpass123",
        full_name="Active Member",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )
    pending_member = User.objects.create_user(
        email="member-count-pending@example.com",
        password="testpass123",
        full_name="Pending Member",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )

    group = StudyGroup.objects.create(
        name="Algorithms Circle",
        description="Practice problems together",
        creator=creator,
        course=course,
        faculty=faculty,
        department=department,
    )

    StudyGroupMember.objects.create(user=creator, group=group, status="active")
    StudyGroupMember.objects.create(user=active_member, group=group, status="active")
    StudyGroupMember.objects.create(user=pending_member, group=group, status="pending")

    response = admin_client.get(reverse("admin_management:study-group-list"))

    assert response.status_code == status.HTTP_200_OK
    result = next(item for item in response.data["results"] if item["id"] == str(group.id))
    assert result["member_count"] == 2


@pytest.mark.django_db
def test_admin_can_archive_study_group(admin_client, study_group_course):
    faculty, department, course = study_group_course
    creator = User.objects.create_user(
        email="archived-owner@example.com",
        password="testpass123",
        full_name="Archive Owner",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )

    group = StudyGroup.objects.create(
        name="Networks Group",
        description="Semester prep",
        creator=creator,
        course=course,
        faculty=faculty,
        department=department,
    )

    response = admin_client.patch(
        reverse("admin_management:study-group-detail", args=[group.id]),
        {"status": "archived"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    group.refresh_from_db()
    assert group.status == "archived"
    assert response.data["status"] == "archived"


@pytest.mark.django_db
def test_backup_download_returns_json_attachment(admin_client, study_group_course):
    _faculty, _department, _course = study_group_course

    response = admin_client.get(
        reverse("admin_management:backup-create"),
        {"download": "1"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("application/json")
    assert "attachment;" in response["Content-Disposition"]
    payload = json.loads(response.content.decode("utf-8"))
    assert "backup" in payload
    assert "data" in payload


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("export_format", "content_type", "extension"),
    [
        ("csv", "text/csv", ".csv"),
        ("pdf", "application/pdf", ".pdf"),
        ("excel", "application/vnd.ms-excel", ".xls"),
    ],
)
def test_export_download_supports_multiple_formats(
    admin_client,
    study_group_course,
    export_format,
    content_type,
    extension,
):
    _faculty, _department, _course = study_group_course

    response = admin_client.get(
        reverse("admin_management:export-data"),
        {"download": "1", "format": export_format},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith(content_type)
    assert extension in response["Content-Disposition"]
    assert response.content
