import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.courses.models import Course
from apps.faculties.models import Department, Faculty
from apps.resources.models import Resource


@pytest.mark.django_db
def test_admin_can_approve_pending_resource(admin_client, admin_user, monkeypatch):
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
    user = User.objects.create_user(
        email="student-review@example.com",
        password="testpass123",
        full_name="Student Reviewer",
        role="student",
        faculty=faculty,
        department=department,
        course=course,
    )

    resource = Resource.objects.create(
        title="Pending moderation item",
        uploaded_by=user,
        faculty=faculty,
        department=department,
        course=course,
        status="pending",
        is_public=False,
    )

    approved_notifications: list[str] = []
    available_notifications: list[str] = []

    monkeypatch.setattr(
        "apps.notifications.services.NotificationService.notify_resource_approved",
        lambda approved_resource: approved_notifications.append(str(approved_resource.id)),
    )
    monkeypatch.setattr(
        "apps.notifications.services.NotificationService.notify_new_resource_available",
        lambda approved_resource: available_notifications.append(str(approved_resource.id)),
    )

    response = admin_client.post(
        reverse("admin_management:resource-approve", args=[resource.id]),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    resource.refresh_from_db()
    assert resource.status == "approved"
    assert resource.is_public is True
    assert resource.approved_by_id == admin_user.id
    assert approved_notifications == [str(resource.id)]
    assert available_notifications == [str(resource.id)]
