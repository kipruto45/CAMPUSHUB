import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.announcements.models import Announcement
from apps.courses.models import Course
from apps.faculties.models import Department, Faculty
from apps.reports.models import Report
from apps.resources.models import Resource
from apps.social.models import StudyGroup


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-stats@example.com",
        password="testpass123",
        full_name="Admin User",
        role="ADMIN",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.mark.django_db
def test_system_stats_returns_live_counts_for_dashboard_cards(admin_client, admin_user):
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

    active_student = User.objects.create_user(
        email="student-one@example.com",
        password="testpass123",
        full_name="Student One",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )
    suspended_student = User.objects.create_user(
        email="student-two@example.com",
        password="testpass123",
        full_name="Student Two",
        role="STUDENT",
        is_active=False,
        faculty=faculty,
        department=department,
        course=course,
    )

    User.objects.filter(id=active_student.id).update(last_login=timezone.now())

    approved_resource = Resource.objects.create(
        title="Approved Resource",
        uploaded_by=active_student,
        faculty=faculty,
        department=department,
        course=course,
        status="approved",
        download_count=4,
        share_count=1,
    )
    pending_resource = Resource.objects.create(
        title="Flagged Resource",
        uploaded_by=suspended_student,
        faculty=faculty,
        department=department,
        course=course,
        status="flagged",
        is_public=False,
        download_count=5,
    )
    Report.objects.create(
        reporter=active_student,
        resource=approved_resource,
        reason_type="spam",
        message="Spam upload",
        status="open",
    )
    Report.objects.create(
        reporter=suspended_student,
        resource=approved_resource,
        reason_type="duplicate",
        message="Duplicate upload",
        status="resolved",
    )

    Resource.objects.filter(id=approved_resource.id).update(status="approved")
    Resource.objects.filter(id=pending_resource.id).update(status="flagged", is_public=False)

    Announcement.objects.create(
        title="Maintenance Window",
        content="Maintenance notice",
        created_by=admin_user,
    )
    Announcement.objects.create(
        title="Semester Update",
        content="Academic update",
        created_by=admin_user,
    )

    StudyGroup.objects.create(
        name="Algorithms Group",
        description="Group for algorithms discussions",
        creator=active_student,
        course=course,
        faculty=faculty,
        department=department,
    )

    response = admin_client.get(reverse("admin_management:system-stats"))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["summary"]["total_users"] == 3
    assert response.data["summary"]["total_students"] == 2
    assert response.data["summary"]["total_admins"] == 1
    assert response.data["summary"]["total_resources"] == 2
    assert response.data["summary"]["pending_resources"] == 1
    assert response.data["summary"]["approved_resources"] == 1
    assert response.data["summary"]["reported_resources"] == 1
    assert response.data["summary"]["total_downloads"] == 9
    assert response.data["summary"]["total_study_groups"] == 1
    assert response.data["summary"]["total_announcements"] == 2
    assert response.data["summary"]["active_users_today"] == 1
    assert response.data["summary"]["suspended_users"] == 1
