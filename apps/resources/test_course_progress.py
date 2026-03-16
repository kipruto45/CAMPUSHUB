import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.downloads.models import Download
from apps.resources.models import CourseProgress, Resource


@pytest.fixture
def academic_context(db):
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering", code="ENG")
    department = faculty.departments.create(name="Computer Science", code="CS")
    course = department.courses.create(name="Computer Science", code="CS")
    return {
        "faculty": faculty,
        "department": department,
        "course": course,
    }


@pytest.fixture
def student(db, academic_context):
    return User.objects.create_user(
        email="student@example.com",
        password="testpass123",
        full_name="Student User",
        role="STUDENT",
        faculty=academic_context["faculty"],
        department=academic_context["department"],
        course=academic_context["course"],
        year_of_study=1,
        semester=1,
    )


@pytest.fixture
def authenticated_client(student):
    client = APIClient()
    refresh = RefreshToken.for_user(student)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def year_one_resource(db, student, academic_context):
    return Resource.objects.create(
        title="Year 1 Notes",
        description="Semester one notes",
        file="year-one.pdf",
        file_type="pdf",
        file_size=1024,
        uploaded_by=student,
        faculty=academic_context["faculty"],
        department=academic_context["department"],
        course=academic_context["course"],
        semester="1",
        year_of_study=1,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def year_two_resource(db, student, academic_context):
    return Resource.objects.create(
        title="Year 2 Notes",
        description="Semester two notes",
        file="year-two.pdf",
        file_type="pdf",
        file_size=1024,
        uploaded_by=student,
        faculty=academic_context["faculty"],
        department=academic_context["department"],
        course=academic_context["course"],
        semester="2",
        year_of_study=2,
        status="approved",
        is_public=True,
    )


@pytest.mark.django_db
def test_mobile_resource_detail_creates_real_view_progress(
    authenticated_client,
    student,
    academic_context,
    year_one_resource,
    year_two_resource,
):
    response = authenticated_client.get(f"/api/mobile/resources/{year_one_resource.id}/")

    assert response.status_code == 200

    progress = CourseProgress.objects.get(user=student, resource=year_one_resource)
    assert progress.course_id == academic_context["course"].id
    assert progress.status == "in_progress"
    assert progress.completion_percentage == 50

    summary_response = authenticated_client.get("/api/courses/progress/")
    assert summary_response.status_code == 200

    payload = summary_response.json()
    assert len(payload) == 1
    summary = payload[0]
    assert summary["course_id"] == str(academic_context["course"].id)
    assert summary["total_resources"] == 1
    assert summary["completed_resources"] == 0
    assert summary["in_progress_resources"] == 1
    assert summary["overall_percentage"] == 50.0


@pytest.mark.django_db
def test_course_progress_summary_uses_download_history_even_without_progress_row(
    authenticated_client,
    student,
    academic_context,
    year_one_resource,
):
    Download.objects.create(user=student, resource=year_one_resource)
    CourseProgress.objects.filter(user=student, course=academic_context["course"]).delete()

    response = authenticated_client.get("/api/courses/progress/")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    summary = payload[0]
    assert summary["course_id"] == str(academic_context["course"].id)
    assert summary["total_resources"] == 1
    assert summary["completed_resources"] == 1
    assert summary["in_progress_resources"] == 0
    assert summary["overall_percentage"] == 100.0
