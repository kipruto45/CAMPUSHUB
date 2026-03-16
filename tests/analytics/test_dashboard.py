import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.downloads.models import Download
from apps.resources.models import Resource


@pytest.mark.django_db
def test_admin_analytics_dashboard_returns_ui_ready_payload(
    admin_client, admin_user, faculty, department, course
):
    student = User.objects.create_user(
        email="analytics-student@example.com",
        password="testpass123",
        full_name="Analytics Student",
        role="STUDENT",
        faculty=faculty,
        department=department,
        course=course,
    )
    User.objects.filter(id=student.id).update(last_login=timezone.now())

    top_resource = Resource.objects.create(
        title="Analytics Notes",
        uploaded_by=student,
        faculty=faculty,
        department=department,
        course=course,
        status="approved",
        resource_type="notes",
        file_size=1024,
        view_count=5,
        download_count=2,
    )
    Resource.objects.create(
        title="Analytics Assignment",
        uploaded_by=student,
        faculty=faculty,
        department=department,
        course=course,
        status="approved",
        resource_type="assignment",
        file_size=2048,
        view_count=1,
        download_count=1,
    )

    Download.objects.create(user=student, resource=top_resource)
    Download.objects.create(user=student, resource=top_resource)

    response = admin_client.get(reverse("analytics:dashboard"), {"period": "month"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["users"]["total"] == 2
    assert response.data["resources"]["total"] == 2
    assert response.data["downloads"]["total"] == 2

    overview = response.data["overview"]
    assert overview["total_users"] == 2
    assert overview["total_resources"] == 2
    assert overview["total_downloads"] == 2
    assert overview["total_uploads"] == 2
    assert overview["active_users"] == 1
    assert overview["storage_used"] == 3072

    assert response.data["trends"]
    assert response.data["top_resources"][0]["title"] == "Analytics Notes"
    assert response.data["top_resources"][0]["download_count"] == 2
    assert response.data["top_resources"][0]["view_count"] == 5
    assert response.data["resource_types"] == [
        {"type": "assignment", "count": 1, "percentage": 50.0},
        {"type": "notes", "count": 1, "percentage": 50.0},
    ]
