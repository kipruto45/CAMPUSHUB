import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty
from apps.resources.models import Resource


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mobile-upload@example.com",
        password="testpass123",
        full_name="Mobile Upload User",
    )


@pytest.fixture
def authenticated_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def public_client():
    return APIClient()


@pytest.fixture
def course_context(db):
    faculty = Faculty.objects.create(name="Engineering", code="ENG")
    department = Department.objects.create(
        faculty=faculty,
        name="Computer Science",
        code="CS",
    )
    course = Course.objects.create(
        department=department,
        name="Computer Science",
        code="BCSC",
    )
    unit = Unit.objects.create(
        course=course,
        name="Data Communication",
        code="BCSC 2203",
        semester="2",
        year_of_study=2,
    )
    return {
        "faculty": faculty,
        "department": department,
        "course": course,
        "unit": unit,
    }


@pytest.mark.django_db
def test_mobile_upload_requires_explicit_academic_selection_and_derives_year_from_unit(
    authenticated_client, course_context, user
):
    response = authenticated_client.post(
        "/api/mobile/resources/upload/",
        {
            "title": "Lecture Notes",
            "resource_type": "tutorial",
            "semester": "2",
            "year_of_study": "2",
            "faculty": str(course_context["faculty"].id),
            "department": str(course_context["department"].id),
            "course": str(course_context["course"].id),
            "unit": str(course_context["unit"].id),
            "file": SimpleUploadedFile(
                "lecture-notes.pdf",
                b"%PDF-1.4 test pdf",
                content_type="application/pdf",
            ),
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True

    resource = Resource.objects.get(title="Lecture Notes", uploaded_by=user)
    assert response.data["data"]["status"] == "approved"
    assert resource.status == "approved"
    assert resource.is_public is True
    assert resource.resource_type == "tutorial"
    assert resource.course_id == course_context["course"].id
    assert resource.department_id == course_context["department"].id
    assert resource.faculty_id == course_context["faculty"].id
    assert resource.unit_id == course_context["unit"].id
    assert resource.semester == "2"
    assert resource.year_of_study == 2


@pytest.mark.django_db
def test_owner_can_update_auto_approved_resource(authenticated_client, course_context, user):
    resource = Resource.objects.create(
        title="Original Title",
        uploaded_by=user,
        faculty=course_context["faculty"],
        department=course_context["department"],
        course=course_context["course"],
        unit=course_context["unit"],
        semester="2",
        year_of_study=2,
        status="approved",
        is_public=True,
        file_size=128,
        file_type="pdf",
        normalized_filename="original-title.pdf",
    )

    response = authenticated_client.patch(
        f"/api/resources/{resource.id}/",
        {
            "title": "Updated Title",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    resource.refresh_from_db()
    assert resource.title == "Updated Title"
    assert resource.status == "approved"
    assert resource.is_public is True


@pytest.mark.django_db
def test_mobile_upload_rejects_missing_faculty_department_and_unit(
    authenticated_client, course_context
):
    response = authenticated_client.post(
        "/api/mobile/resources/upload/",
        {
            "title": "Incomplete Upload",
            "course": str(course_context["course"].id),
            "file": SimpleUploadedFile(
                "incomplete.pdf",
                b"%PDF-1.4 test pdf",
                content_type="application/pdf",
            ),
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["success"] is False
    assert "semester" in response.data["error"]["details"]
    assert "year_of_study" in response.data["error"]["details"]
    assert "faculty" in response.data["error"]["details"]
    assert "department" in response.data["error"]["details"]
    assert "unit" in response.data["error"]["details"]


@pytest.mark.django_db
def test_mobile_upload_rejects_year_or_semester_that_do_not_match_selected_unit(
    authenticated_client, course_context
):
    response = authenticated_client.post(
        "/api/mobile/resources/upload/",
        {
            "title": "Mismatch Upload",
            "semester": "1",
            "year_of_study": "1",
            "faculty": str(course_context["faculty"].id),
            "department": str(course_context["department"].id),
            "course": str(course_context["course"].id),
            "unit": str(course_context["unit"].id),
            "file": SimpleUploadedFile(
                "mismatch.pdf",
                b"%PDF-1.4 test pdf",
                content_type="application/pdf",
            ),
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["success"] is False
    assert "semester" in response.data["error"]["details"]


@pytest.mark.django_db
def test_public_courses_can_be_filtered_by_year_and_semester(public_client, course_context):
    non_matching_course = Course.objects.create(
        department=course_context["department"],
        name="Information Technology",
        code="BCIT",
    )
    Unit.objects.create(
        course=non_matching_course,
        name="Programming Fundamentals",
        code="BCIT 1101",
        semester="1",
        year_of_study=1,
    )

    response = public_client.get(
        "/api/public/courses/",
        {
            "department_id": str(course_context["department"].id),
            "semester": "2",
            "year_of_study": "2",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    course_ids = {str(course["id"]) for course in response.data["data"]["courses"]}
    assert course_ids == {str(course_context["course"].id)}


@pytest.mark.django_db
def test_mobile_units_can_be_filtered_by_year_and_semester(
    authenticated_client, course_context
):
    Unit.objects.create(
        course=course_context["course"],
        name="Programming Basics",
        code="BCSC 1101",
        semester="1",
        year_of_study=1,
    )

    response = authenticated_client.get(
        f"/api/mobile/courses/{course_context['course'].id}/units/",
        {
            "semester": "2",
            "year_of_study": "2",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert [
        {
            **unit,
            "id": str(unit["id"]),
        }
        for unit in response.data["data"]["units"]
    ] == [
        {
            "id": str(course_context["unit"].id),
            "name": "Data Communication",
            "code": "BCSC 2203",
            "semester": "2",
            "year_of_study": 2,
        }
    ]


@pytest.mark.django_db
def test_upload_academic_endpoints_expose_active_admin_managed_records_only(
    authenticated_client, public_client, course_context
):
    Faculty.objects.create(name="Inactive Faculty", code="IFAC", is_active=False)
    Department.objects.create(
        faculty=course_context["faculty"],
        name="Inactive Department",
        code="IDEP",
        is_active=False,
    )
    Course.objects.create(
        department=course_context["department"],
        name="Inactive Course",
        code="ICRS",
        is_active=False,
    )
    Unit.objects.create(
        course=course_context["course"],
        name="Inactive Unit",
        code="BCSC 2204",
        semester="2",
        year_of_study=2,
        is_active=False,
    )

    faculties_response = public_client.get("/api/public/faculties/")
    assert faculties_response.status_code == status.HTTP_200_OK
    assert {faculty["code"] for faculty in faculties_response.data["data"]["faculties"]} == {
        course_context["faculty"].code
    }

    departments_response = public_client.get(
        "/api/public/departments/",
        {"faculty_id": str(course_context["faculty"].id)},
    )
    assert departments_response.status_code == status.HTTP_200_OK
    assert {
        department["code"]
        for department in departments_response.data["data"]["departments"]
    } == {course_context["department"].code}

    courses_response = public_client.get(
        "/api/public/courses/",
        {
            "department_id": str(course_context["department"].id),
            "semester": "2",
            "year_of_study": "2",
        },
    )
    assert courses_response.status_code == status.HTTP_200_OK
    assert {
        course["code"] for course in courses_response.data["data"]["courses"]
    } == {course_context["course"].code}

    units_response = authenticated_client.get(
        f"/api/mobile/courses/{course_context['course'].id}/units/",
        {
            "semester": "2",
            "year_of_study": "2",
        },
    )
    assert units_response.status_code == status.HTTP_200_OK
    assert {
        unit["code"] for unit in units_response.data["data"]["units"]
    } == {course_context["unit"].code}
