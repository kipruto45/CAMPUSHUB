import pytest
from django.contrib.auth import get_user_model
from unittest.mock import patch

from apps.certificates.models import Certificate
from apps.certificates.services import CertificateService


@pytest.mark.django_db
@patch.object(CertificateService, "generate_certificate", return_value=None)
def test_create_custom_certificate_from_collection_endpoint(
    _mock_generate_certificate, authenticated_client, user
):
    payload = {
        "certificate_type": "custom",
        "user_id": user.id,
        "title": "CampusHub Contributor",
        "description": "Awarded for helping peers",
        "issuing_authority": "CampusHub",
    }

    response = authenticated_client.post("/api/certificates/", payload, format="json")

    assert response.status_code == 201
    assert response.data["title"] == payload["title"]
    assert response.data["user"]["id"] == user.id
    assert response.data["unique_id"].startswith("CERT-")
    assert Certificate.objects.filter(user=user, title=payload["title"]).exists()


@pytest.mark.django_db
@patch.object(CertificateService, "generate_certificate", return_value=None)
def test_create_custom_certificate_from_generate_endpoint(
    _mock_generate_certificate, authenticated_client, user
):
    payload = {
        "certificate_type": "custom",
        "user_id": user.id,
        "title": "Course Mentor",
        "description": "Issued for outstanding mentorship",
        "issuing_authority": "CampusHub",
    }

    response = authenticated_client.post(
        "/api/certificates/generate/",
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["title"] == payload["title"]
    assert response.data["user"]["id"] == user.id


@pytest.mark.django_db
def test_generate_certificate_returns_404_for_missing_user(authenticated_client):
    payload = {
        "certificate_type": "custom",
        "user_id": 999999,
        "title": "Invalid User Certificate",
        "description": "This should fail",
    }

    response = authenticated_client.post(
        "/api/certificates/generate/",
        payload,
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"] == "User not found"


@pytest.mark.django_db
@patch.object(CertificateService, "generate_certificate", return_value=None)
def test_user_certificate_list_uses_integer_route_param(
    _mock_generate_certificate, authenticated_client, user
):
    other_user = get_user_model().objects.create_user(
        email="other-cert-user@test.com",
        password="Passw0rd!",
        full_name="Other Cert User",
        registration_number="OTHER-CERT-001",
        role="student",
    )

    service = CertificateService()
    service.create_custom_certificate(
        user=user,
        title="User One Certificate",
        description="Owned by first user",
        issued_by=user,
    )
    service.create_custom_certificate(
        user=other_user,
        title="User Two Certificate",
        description="Owned by second user",
        issued_by=user,
    )

    response = authenticated_client.get(f"/api/certificates/user/{user.id}/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "User One Certificate"
