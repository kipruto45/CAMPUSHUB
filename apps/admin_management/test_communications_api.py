from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.admin_management.models import (
    AdminInvitationRole,
    AdminRoleInvitation,
    AdminRoleInvitationRole,
)
from apps.admin_management.services import send_role_invitation_email
from apps.core.models import EmailCampaign
from apps.notifications.models import Notification


def _role_definition(code: str, **defaults) -> AdminInvitationRole:
    role, _created = AdminInvitationRole.objects.get_or_create(
        code=code,
        defaults={
            "name": defaults.pop("name", code.replace("_", " ").title()),
            **defaults,
        },
    )
    return role


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="communications-admin@example.com",
        password="testpass123",
        full_name="Communications Admin",
        role="ADMIN",
        is_verified=True,
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.mark.django_db
@patch("apps.admin_management.services.EmailService.send_email", return_value=True)
def test_role_invitation_email_includes_code_and_links(mock_send_email, admin_user, settings):
    settings.FRONTEND_BASE_URL = "https://campushub.example"
    settings.FRONTEND_URL = ""

    role_definition = _role_definition("INSTRUCTOR", name="Instructor")
    invitation = AdminRoleInvitation.objects.create(
        email="invitee@example.com",
        role=role_definition.code,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    AdminRoleInvitationRole.objects.create(
        invitation=invitation,
        role_definition=role_definition,
        is_primary=True,
    )

    sent = send_role_invitation_email(invitation=invitation)

    assert sent is True
    kwargs = mock_send_email.call_args.kwargs
    assert kwargs["recipient_list"] == ["invitee@example.com"]
    message = kwargs["message"]
    assert f"Invitation code: {invitation.token}" in message
    assert f"https://campushub.example/role-invite/{invitation.token}/" in message
    assert (
        f"https://campushub.example/role-invite?token={invitation.token}" in message
    )


@pytest.mark.django_db
@patch("apps.admin_management.services.EmailService.send_email", return_value=True)
def test_role_invitation_email_falls_back_to_backend_absolute_link(
    mock_send_email,
    admin_user,
    settings,
):
    settings.FRONTEND_BASE_URL = ""
    settings.FRONTEND_URL = ""
    settings.RESOURCE_SHARE_BASE_URL = ""
    settings.WEB_APP_URL = ""
    settings.MOBILE_DEEPLINK_SCHEME = ""
    settings.BASE_URL = "https://api.campushub.example"

    role_definition = _role_definition("INSTRUCTOR", name="Instructor")
    invitation = AdminRoleInvitation.objects.create(
        email="invitee@example.com",
        role=role_definition.code,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    AdminRoleInvitationRole.objects.create(
        invitation=invitation,
        role_definition=role_definition,
        is_primary=True,
    )

    sent = send_role_invitation_email(invitation=invitation)

    assert sent is True
    message = mock_send_email.call_args.kwargs["message"]
    assert f"https://api.campushub.example/role-invite/{invitation.token}/" in message
    assert "Open directly in app:" not in message


@pytest.mark.django_db
@patch(
    "apps.admin_management.services.AdminEmailService.send_campaign_emails",
    return_value={"sent_count": 1, "failed_count": 0},
)
@patch(
    "apps.admin_management.services.get_sms_configuration_status",
    return_value={"configured": True, "message": "configured"},
)
@patch(
    "apps.admin_management.services.sms_service.send",
    return_value={"success": True, "status": "Sent"},
)
def test_admin_can_send_multi_channel_communication(
    _mock_sms_send,
    _mock_sms_status,
    _mock_send_campaign,
    admin_client,
):
    student = User.objects.create_user(
        email="student-target@example.com",
        password="testpass123",
        full_name="Target Student",
        role="STUDENT",
        is_verified=True,
        phone_number="+254700000001",
    )
    User.objects.create_user(
        email="staff-other@example.com",
        password="testpass123",
        full_name="Other Staff",
        role="SUPPORT_STAFF",
        is_verified=True,
        phone_number="+254700000002",
    )

    response = admin_client.post(
        reverse("admin_management:communications-send"),
        {
            "title": "Campus update",
            "email_subject": "Campus update for students",
            "message": "Classes resume on Monday.",
            "sms_message": "CampusHub: Classes resume Monday.",
            "link": "/announcements/classes-resume",
            "channels": ["email", "in_app", "sms"],
            "target_user_roles": ["STUDENT"],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["recipient_count"] == 1
    assert response.data["channel_results"]["email"]["sent_count"] == 1
    assert response.data["channel_results"]["in_app"]["sent_count"] == 1
    assert response.data["channel_results"]["sms"]["sent_count"] == 1

    assert Notification.objects.filter(
        recipient=student,
        title="Campus update",
        message="Classes resume on Monday.",
        link="/announcements/classes-resume",
    ).exists()

    campaign = EmailCampaign.objects.get(name="Campus update")
    assert campaign.subject == "Campus update for students"
    assert campaign.recipient_count == 1
    assert campaign.target_filters == {"user_roles": ["STUDENT"]}


@pytest.mark.django_db
def test_admin_communication_requires_matching_recipients(admin_client):
    response = admin_client.post(
        reverse("admin_management:communications-send"),
        {
            "title": "Faculty notice",
            "message": "This audience does not exist.",
            "channels": ["in_app"],
            "target_user_roles": ["MODERATOR"],
            "target_year_of_study": 9,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "No active users matched the selected audience."
