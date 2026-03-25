import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.resources.models import PersonalFolder, PersonalResource, Resource


@pytest.fixture
def academic_context(db):
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering", code="ENG")
    department = faculty.departments.create(name="Computer Science", code="CS")
    course = department.courses.create(name="Computer Science", code="BCS")
    unit = course.units.create(name="Algorithms", code="CSC201")
    return {
        "faculty": faculty,
        "department": department,
        "course": course,
        "unit": unit,
    }


@pytest.fixture
def student(db, academic_context):
    return User.objects.create_user(
        email="library-student@example.com",
        password="testpass123",
        full_name="Library Student",
        role="STUDENT",
        faculty=academic_context["faculty"],
        department=academic_context["department"],
        course=academic_context["course"],
        year_of_study=2,
        semester=1,
    )


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email="uploader@example.com",
        password="testpass123",
        full_name="Resource Uploader",
    )


@pytest.fixture
def authenticated_client(student):
    client = APIClient()
    refresh = RefreshToken.for_user(student)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def approved_resource(db, uploader, academic_context):
    return Resource.objects.create(
        title="Algorithms Exam Pack",
        description="Past paper collection for revision.",
        resource_type="past_paper",
        file="algorithms-exam-pack.pdf",
        file_type="pdf",
        file_size=4096,
        uploaded_by=uploader,
        faculty=academic_context["faculty"],
        department=academic_context["department"],
        course=academic_context["course"],
        unit=academic_context["unit"],
        status="approved",
        is_public=True,
    )


@pytest.mark.django_db
def test_save_to_library_creates_type_folder_and_personal_copy(
    authenticated_client,
    student,
    approved_resource,
):
    response = authenticated_client.post(f"/api/resources/{approved_resource.id}/save/")

    assert response.status_code == 201
    assert response.data["already_saved"] is False
    assert response.data["folder"]["name"] == "Past Papers"

    folder = PersonalFolder.objects.get(
        user=student,
        name="Past Papers",
        parent__isnull=True,
    )
    saved_item = PersonalResource.objects.get(
        user=student,
        linked_public_resource=approved_resource,
    )

    assert saved_item.folder_id == folder.id
    assert saved_item.source_type == "saved"
    assert saved_item.title == approved_resource.title


@pytest.mark.django_db
def test_save_to_library_is_idempotent_for_existing_personal_copy(
    authenticated_client,
    student,
    approved_resource,
):
    first_response = authenticated_client.post(
        f"/api/resources/{approved_resource.id}/save/"
    )
    second_response = authenticated_client.post(
        f"/api/resources/{approved_resource.id}/save/"
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.data["already_saved"] is True
    assert (
        PersonalResource.objects.filter(
            user=student,
            linked_public_resource=approved_resource,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_resource_detail_reports_personal_library_state_and_target_folder(
    authenticated_client,
    student,
    approved_resource,
):
    folder = PersonalFolder.objects.create(
        user=student,
        name="Past Papers",
        color="#f59e0b",
    )
    PersonalResource.objects.create(
        user=student,
        folder=folder,
        title=approved_resource.title,
        file=approved_resource.file,
        file_type=approved_resource.file_type,
        file_size=approved_resource.file_size,
        description=approved_resource.description,
        tags=approved_resource.tags,
        visibility="private",
        source_type="saved",
        linked_public_resource=approved_resource,
    )

    response = authenticated_client.get(f"/api/resources/{approved_resource.slug}/")

    assert response.status_code == 200
    assert response.data["is_in_my_library"] is True
    assert response.data["default_library_folder_name"] == "Past Papers"


@pytest.mark.django_db
def test_mobile_save_to_library_uses_type_folder_response(
    authenticated_client,
    approved_resource,
):
    response = authenticated_client.post(
        f"/api/mobile/resources/{approved_resource.id}/save-to-library/"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["already_saved"] is False
    assert payload["data"]["folder"]["name"] == "Past Papers"
