"""Tests for courses and units API views."""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty


@pytest.fixture
def faculty_two(db):
    return Faculty.objects.create(name="Engineering", code="ENG")


@pytest.fixture
def department_two(db, faculty_two):
    return Department.objects.create(
        faculty=faculty_two,
        name="Mechanical Engineering",
        code="ME",
    )


@pytest.fixture
def course_two(db, department_two):
    return Course.objects.create(
        department=department_two,
        name="Bachelor of Mechanical Engineering",
        code="BME",
        duration_years=5,
    )


@pytest.mark.django_db
class TestCourseViewSet:
    """Cover course list/filter/detail/create/update/delete behavior."""

    def test_course_list_filters(
        self, api_client, faculty, department, course, faculty_two, department_two, course_two
    ):
        # department_id filter
        by_dept = api_client.get(f"/api/courses/?department_id={department.id}")
        assert by_dept.status_code == status.HTTP_200_OK
        assert by_dept.data["count"] == 1
        assert by_dept.data["results"][0]["id"] == str(course.id)

        # department_slug filter
        by_dept_slug = api_client.get(
            f"/api/courses/?department_slug={department_two.slug}"
        )
        assert by_dept_slug.status_code == status.HTTP_200_OK
        assert by_dept_slug.data["count"] == 1
        assert by_dept_slug.data["results"][0]["id"] == str(course_two.id)

        # faculty_id filter
        by_faculty = api_client.get(f"/api/courses/?faculty_id={faculty.id}")
        assert by_faculty.status_code == status.HTTP_200_OK
        assert by_faculty.data["count"] == 1
        assert by_faculty.data["results"][0]["id"] == str(course.id)

    def test_course_retrieve_uses_detail_serializer(self, api_client, course, unit):
        response = api_client.get(f"/api/courses/{course.slug}/")
        assert response.status_code == status.HTTP_200_OK
        assert "units" in response.data
        assert "department_details" in response.data

    def test_course_create_permissions(self, user, admin_user, department):
        payload = {
            "department": str(department.id),
            "name": "BSc Computer Engineering",
            "code": "BCE",
            "duration_years": 4,
        }
        anonymous = APIClient().post("/api/courses/", payload, format="json")
        assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED

        student_client = APIClient()
        student_client.force_authenticate(user=user)
        student = student_client.post("/api/courses/", payload, format="json")
        assert student.status_code == status.HTTP_403_FORBIDDEN

        privileged_client = APIClient()
        privileged_client.force_authenticate(user=admin_user)
        admin = privileged_client.post("/api/courses/", payload, format="json")
        assert admin.status_code == status.HTTP_201_CREATED
        assert admin.data["name"] == "BSc Computer Engineering"

    def test_course_update_and_soft_delete(self, admin_client, department):
        course = Course.objects.create(
            department=department,
            name="Temporary Course",
            code="TMP",
            duration_years=3,
        )
        patch_response = admin_client.patch(
            f"/api/courses/{course.slug}/",
            {"name": "Updated Course Name"},
            format="json",
        )
        assert patch_response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert course.name == "Updated Course Name"

        delete_response = admin_client.delete(f"/api/courses/{course.slug}/")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        course.refresh_from_db()
        assert course.is_active is False


@pytest.mark.django_db
class TestUnitViewSet:
    """Cover unit list/filter/create/update/delete behavior."""

    def test_unit_list_filters(self, api_client, department, course, unit, course_two):
        other_unit = Unit.objects.create(
            course=course_two,
            name="Thermodynamics",
            code="ME201",
            semester="2",
            year_of_study=2,
        )

        by_course_id = api_client.get(f"/api/units/?course_id={course.id}")
        assert by_course_id.status_code == status.HTTP_200_OK
        assert by_course_id.data["count"] == 1
        assert by_course_id.data["results"][0]["id"] == str(unit.id)

        by_course_slug = api_client.get(f"/api/units/?course_slug={course_two.slug}")
        assert by_course_slug.status_code == status.HTTP_200_OK
        assert by_course_slug.data["count"] == 1
        assert by_course_slug.data["results"][0]["id"] == str(other_unit.id)

        by_department = api_client.get(f"/api/units/?department_id={department.id}")
        assert by_department.status_code == status.HTTP_200_OK
        assert by_department.data["count"] == 1
        assert by_department.data["results"][0]["id"] == str(unit.id)

        by_semester = api_client.get("/api/units/?semester=1")
        assert by_semester.status_code == status.HTTP_200_OK
        assert any(item["id"] == str(unit.id) for item in by_semester.data["results"])

        by_year = api_client.get("/api/units/?year=2")
        assert by_year.status_code == status.HTTP_200_OK
        assert all(item["year_of_study"] == 2 for item in by_year.data["results"])

    def test_unit_create_update_soft_delete_permissions(
        self, user, admin_user, course
    ):
        payload = {
            "course": str(course.id),
            "name": "Operating Systems",
            "code": "CS301",
            "semester": "1",
            "year_of_study": 3,
        }

        anonymous = APIClient().post("/api/units/", payload, format="json")
        assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED

        student_client = APIClient()
        student_client.force_authenticate(user=user)
        student = student_client.post("/api/units/", payload, format="json")
        assert student.status_code == status.HTTP_403_FORBIDDEN

        privileged_client = APIClient()
        privileged_client.force_authenticate(user=admin_user)
        created = privileged_client.post("/api/units/", payload, format="json")
        assert created.status_code == status.HTTP_201_CREATED
        slug = created.data["slug"]

        patched = privileged_client.patch(
            f"/api/units/{slug}/",
            {"name": "Advanced Operating Systems"},
            format="json",
        )
        assert patched.status_code == status.HTTP_200_OK

        deleted = privileged_client.delete(f"/api/units/{slug}/")
        assert deleted.status_code == status.HTTP_204_NO_CONTENT
        assert Unit.objects.get(slug=slug).is_active is False

    def test_public_list_views(self, api_client):
        assert api_client.get("/api/courses/public/").status_code == status.HTTP_200_OK
        assert api_client.get("/api/units/public/").status_code == status.HTTP_200_OK
