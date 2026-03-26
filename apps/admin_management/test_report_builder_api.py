import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-report-builder@example.com",
        password="testpass123",
        full_name="Report Builder Admin",
        role="ADMIN",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.mark.django_db
def test_report_builder_alias_lists_available_reports(admin_client, monkeypatch):
    from apps.admin_management.report_builder import ReportBuilderService

    expected_reports = [
        {
            "id": "user_activity",
            "name": "User Activity Report",
            "description": "Detailed user activity and engagement metrics",
            "filters": ["date_range"],
            "fields": ["user", "activity_type"],
        }
    ]

    monkeypatch.setattr(
        ReportBuilderService,
        "get_available_reports",
        staticmethod(lambda: expected_reports),
    )

    response = admin_client.get(reverse("admin_management:report-builder-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["reports"] == expected_reports


@pytest.mark.django_db
def test_report_builder_alias_generates_reports(admin_client, monkeypatch):
    from apps.admin_management.report_builder import ReportBuilderService

    generated_payload = {
        "report_type": "resource_usage",
        "generated_at": "2026-03-26T12:00:00",
        "record_count": 4,
        "filters": {"faculty": "1"},
        "format": "csv",
        "data": None,
        "csv_data": "title,downloads\nAlgorithms,12\n",
    }

    monkeypatch.setattr(
        ReportBuilderService,
        "generate_report",
        staticmethod(
            lambda report_type, filters=None, fields=None, format="json": generated_payload
        ),
    )

    response = admin_client.post(
        reverse("admin_management:report-builder-generate"),
        {
            "report_type": "resource_usage",
            "filters": {"faculty": "1"},
            "format": "csv",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == generated_payload


@pytest.mark.django_db
def test_bulk_resource_update_endpoint_returns_service_result(admin_client, monkeypatch):
    from apps.admin_management.report_builder import BulkOperationsService

    monkeypatch.setattr(
        BulkOperationsService,
        "bulk_update_resources",
        staticmethod(
            lambda resource_ids, updates: {
                "success": True,
                "updated_count": len(resource_ids),
                "total_requested": len(resource_ids),
                "updates": updates,
            }
        ),
    )

    response = admin_client.post(
        reverse("admin_management:bulk-resource-update"),
        {
            "resource_ids": ["resource-1", "resource-2"],
            "updates": {"status": "approved"},
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["updated_count"] == 2
    assert response.data["updates"] == {"status": "approved"}
