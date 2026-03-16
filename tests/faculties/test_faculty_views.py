"""Tests for faculties and departments API views."""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.faculties.models import Department, Faculty


@pytest.fixture
def faculty_two(db):
    return Faculty.objects.create(name="Education", code="EDU")


@pytest.fixture
def department_two(db, faculty_two):
    return Department.objects.create(
        faculty=faculty_two,
        name="Curriculum Studies",
        code="CUR",
    )


@pytest.mark.django_db
class TestFacultyEndpoints:
    """Validate faculty list/detail and restricted write operations."""

    def test_public_faculty_list(self, api_client, faculty, faculty_two):
        response = api_client.get("/api/faculties/public/")
        assert response.status_code == status.HTTP_200_OK
        ids = {item["id"] for item in response.data["results"]}
        assert str(faculty.id) in ids
        assert str(faculty_two.id) in ids

    def test_faculty_retrieve_uses_detail_serializer(self, api_client, faculty, department):
        response = api_client.get(f"/api/faculties/{faculty.slug}/")
        assert response.status_code == status.HTTP_200_OK
        assert "departments" in response.data
        department_ids = {item["id"] for item in response.data["departments"]}
        assert str(department.id) in department_ids

    def test_faculty_create_update_delete_permissions(self, user, admin_user):
        payload = {
            "name": "Health Sciences",
            "code": "HS",
            "description": "Medical and allied health programs",
        }

        anonymous = APIClient().post("/api/faculties/", payload, format="json")
        assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED

        student_client = APIClient()
        student_client.force_authenticate(user=user)
        student = student_client.post("/api/faculties/", payload, format="json")
        assert student.status_code == status.HTTP_403_FORBIDDEN

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        created = admin_client.post("/api/faculties/", payload, format="json")
        assert created.status_code == status.HTTP_201_CREATED
        slug = created.data["slug"]

        patched = admin_client.patch(
            f"/api/faculties/{slug}/",
            {"description": "Updated description"},
            format="json",
        )
        assert patched.status_code == status.HTTP_200_OK

        deleted = admin_client.delete(f"/api/faculties/{slug}/")
        assert deleted.status_code == status.HTTP_204_NO_CONTENT
        assert Faculty.objects.get(slug=slug).is_active is False


@pytest.mark.django_db
class TestDepartmentEndpoints:
    """Validate department filters and restricted write operations."""

    def test_department_public_list_filters(
        self, api_client, faculty, department, faculty_two, department_two
    ):
        by_faculty_id = api_client.get(f"/api/departments/public/?faculty_id={faculty.id}")
        assert by_faculty_id.status_code == status.HTTP_200_OK
        assert by_faculty_id.data["count"] == 1
        assert by_faculty_id.data["results"][0]["id"] == str(department.id)

        by_faculty_slug = api_client.get(
            f"/api/departments/public/?faculty_slug={faculty_two.slug}"
        )
        assert by_faculty_slug.status_code == status.HTTP_200_OK
        assert by_faculty_slug.data["count"] == 1
        assert by_faculty_slug.data["results"][0]["id"] == str(department_two.id)

    def test_department_viewset_filters_and_permissions(
        self, user, admin_user, faculty, department, faculty_two, department_two
    ):
        payload = {
            "faculty": str(faculty.id),
            "name": "Information Technology",
            "code": "IT",
            "description": "Technology programs",
        }

        anonymous = APIClient().post("/api/departments/", payload, format="json")
        assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED

        student_client = APIClient()
        student_client.force_authenticate(user=user)
        student = student_client.post("/api/departments/", payload, format="json")
        assert student.status_code == status.HTTP_403_FORBIDDEN

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        created = admin_client.post("/api/departments/", payload, format="json")
        assert created.status_code == status.HTTP_201_CREATED
        slug = created.data["slug"]

        by_faculty_alias = APIClient().get(f"/api/departments/?faculty={faculty.slug}")
        assert by_faculty_alias.status_code == status.HTTP_200_OK
        ids = {item["id"] for item in by_faculty_alias.data["results"]}
        assert str(department.id) in ids
        assert str(created.data["id"]) in ids
        assert str(department_two.id) not in ids

        by_faculty_id = APIClient().get(f"/api/departments/?faculty_id={faculty_two.id}")
        assert by_faculty_id.status_code == status.HTTP_200_OK
        assert by_faculty_id.data["count"] == 1
        assert by_faculty_id.data["results"][0]["id"] == str(department_two.id)

        patched = admin_client.patch(
            f"/api/departments/{slug}/",
            {"name": "ICT"},
            format="json",
        )
        assert patched.status_code == status.HTTP_200_OK

        deleted = admin_client.delete(f"/api/departments/{slug}/")
        assert deleted.status_code == status.HTTP_204_NO_CONTENT
        assert Department.objects.get(slug=slug).is_active is False
