import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.admin_management.api_keys import APIKey
from apps.admin_management.funnel import Funnel
from apps.admin_management.incidents import Incident
from apps.admin_management.models import ContentCalendarEvent
from apps.admin_management.workflows import Workflow, WorkflowExecution
from apps.core.models import AuditLog


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin-ops@example.com",
        password="testpass123",
        full_name="Admin Ops",
        role="ADMIN",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.mark.django_db
def test_content_calendar_event_create_and_filter(admin_client):
    start = timezone.now() + timezone.timedelta(days=1)
    end = start + timezone.timedelta(hours=2)

    create_response = admin_client.post(
        reverse("admin_management:content-calendar-events"),
        {
            "title": "Orientation Push",
            "description": "Send new term announcement",
            "event_type": ContentCalendarEvent.EventType.ANNOUNCEMENT,
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
            "color": "#3B82F6",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["status"] == ContentCalendarEvent.EventStatus.SCHEDULED

    list_response = admin_client.get(
        reverse("admin_management:content-calendar-events"),
        {
            "start_date": (start - timezone.timedelta(hours=1)).isoformat(),
            "end_date": (end + timezone.timedelta(hours=1)).isoformat(),
        },
    )

    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.data) == 1
    assert list_response.data[0]["title"] == "Orientation Push"


@pytest.mark.django_db
def test_incident_status_update_marks_incident_resolved(admin_client, admin_user):
    incident = Incident.objects.create(
        title="API outage",
        description="Intermittent 500 responses",
        incident_type=Incident.IncidentType.OUTAGE,
        severity=Incident.Severity.HIGH,
        reported_by=admin_user,
    )

    response = admin_client.patch(
        reverse("admin_management:incident-status", args=[incident.id]),
        {
            "status": Incident.Status.RESOLVED,
            "resolution": "Scaled workers and cleared stale jobs.",
        },
        format="json",
    )

    incident.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolution == "Scaled workers and cleared stale jobs."
    assert incident.resolved_at is not None


@pytest.mark.django_db
def test_api_key_create_and_revoke_flow(admin_client, admin_user):
    create_response = admin_client.post(
        reverse("admin_management:api-key-list"),
        {
            "name": "CLI access",
            "description": "Used for exports",
            "key_type": APIKey.KeyType.PERSONAL,
            "rate_limit": 500,
            "scopes": ["read", "write"],
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["raw_key"]
    key_id = create_response.data["id"]

    api_key = APIKey.objects.get(id=key_id, user=admin_user)
    assert api_key.rate_limit == 500
    assert api_key.rate_limit_remaining == 500

    revoke_response = admin_client.post(
        reverse("admin_management:api-key-revoke", args=[api_key.id])
    )

    api_key.refresh_from_db()

    assert revoke_response.status_code == status.HTTP_200_OK
    assert api_key.status == APIKey.KeyStatus.REVOKED


@pytest.mark.django_db
def test_audit_log_list_filters_by_action(admin_client, admin_user):
    AuditLog.objects.create(
        action="user_login",
        user=admin_user,
        description="Admin logged in",
        target_type="session",
        target_id=1,
    )
    AuditLog.objects.create(
        action="resource_created",
        user=admin_user,
        description="Created a new resource",
        target_type="resource",
        target_id=2,
    )

    response = admin_client.get(
        reverse("admin_management:audit-log"),
        {"action": "login"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["action"] == "user_login"


@pytest.mark.django_db
def test_workflow_run_endpoint_returns_execution(admin_client, admin_user):
    workflow = Workflow.objects.create(
        name="Manual Review",
        description="Run a one-off maintenance workflow",
        trigger_type=Workflow.TriggerType.MANUAL,
        actions=[],
        status=Workflow.WorkflowStatus.DRAFT,
        created_by=admin_user,
    )

    response = admin_client.post(
        reverse("admin_management:workflow-run", args=[workflow.id])
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == WorkflowExecution.ExecutionStatus.COMPLETED
    assert WorkflowExecution.objects.filter(workflow=workflow).count() == 1


@pytest.mark.django_db
def test_funnel_list_bootstraps_default_funnels(admin_client):
    response = admin_client.get(reverse("admin_management:funnel-list"))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1
    assert Funnel.objects.exists()
