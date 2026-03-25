from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.admin_management.models import (
    AdminInvitationBatch,
    AdminInvitationRole,
    AdminRoleInvitation,
    AdminUserRoleAssignment,
)


def _ensure_role_definition(code: str, name: str | None = None):
    return AdminInvitationRole.objects.get_or_create(
        code=code,
        defaults={
            "name": name or code.replace("_", " ").title(),
            "description": f"{code.title()} access",
            "is_active": True,
            "is_assignable": True,
        },
    )[0]


@pytest.mark.django_db
def test_admin_can_create_role_invitation_and_email_link(admin_client, admin_user):
    mail.outbox.clear()

    response = admin_client.post(
        reverse("admin_management:role-invitation-list"),
        {
            "email": "moderator.invite@test.com",
            "role": "MODERATOR",
            "note": "Please help review resources.",
        },
        format="json",
    )

    assert response.status_code == 201
    invitation = AdminRoleInvitation.objects.get(email="moderator.invite@test.com")
    assert invitation.role == "MODERATOR"
    assert invitation.invited_by == admin_user
    assert response.data["status"] == "pending"
    assert "/role-invite/" in response.data["accept_url"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["moderator.invite@test.com"]
    assert invitation.token in mail.outbox[0].body


@pytest.mark.django_db
def test_admin_can_create_multi_role_invitation(admin_client, admin_user):
    _ensure_role_definition("INSTRUCTOR", "Instructor")
    _ensure_role_definition("DEPARTMENT_HEAD", "Department Head")
    response = admin_client.post(
        reverse("admin_management:role-invitation-list"),
        {
            "email": "faculty.lead@test.com",
            "roles": ["INSTRUCTOR", "DEPARTMENT_HEAD"],
            "note": "Leading the new academic cohort.",
        },
        format="json",
    )

    assert response.status_code == 201
    invitation = AdminRoleInvitation.objects.get(email="faculty.lead@test.com")
    assert set(invitation.get_role_codes()) == {"INSTRUCTOR", "DEPARTMENT_HEAD"}
    assert invitation.role == "DEPARTMENT_HEAD"
    assert response.data["roles"] == ["INSTRUCTOR", "DEPARTMENT_HEAD"]


@pytest.mark.django_db
def test_non_super_admin_cannot_invite_admin_role(api_client):
    _ensure_role_definition("ADMIN", "Admin")
    limited_admin = User.objects.create_user(
        email="limited.admin@test.com",
        password="admin-pass-123",
        full_name="Limited Admin",
        role="ADMIN",
        is_active=True,
        is_verified=True,
    )
    api_client.force_authenticate(user=limited_admin)

    response = api_client.post(
        reverse("admin_management:role-invitation-list"),
        {
            "email": "new.admin.invite@test.com",
            "roles": ["ADMIN"],
        },
        format="json",
    )

    assert response.status_code == 400
    assert "permission" in str(response.data["roles"]).lower()


@pytest.mark.django_db
def test_validate_role_invitation_requires_login_for_existing_account(admin_client, user):
    invitation = AdminRoleInvitation.objects.create(
        email=user.email,
        role="MODERATOR",
        invited_by=user,
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = admin_client.get(
        reverse(
            "admin_management:role-invitation-validate",
            kwargs={"token": invitation.token},
        )
    )

    assert response.status_code == 200
    assert response.data["valid"] is True
    assert response.data["existing_account"] is True
    assert response.data["requires_login"] is True
    assert response.data["can_accept"] is False


@pytest.mark.django_db
def test_accept_role_invitation_creates_new_user(admin_user):
    invitation = AdminRoleInvitation.objects.create(
        email="new.admin@test.com",
        role="ADMIN",
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )

    anonymous_client = APIClient()
    response = anonymous_client.post(
        reverse("admin_management:role-invitation-accept"),
        {
            "token": invitation.token,
            "full_name": "New Admin",
            "password": "secure-pass-123",
            "password_confirm": "secure-pass-123",
        },
        format="json",
    )

    assert response.status_code == 201
    created_user = User.objects.get(email="new.admin@test.com")
    invitation.refresh_from_db()
    assert created_user.role == "ADMIN"
    assert created_user.is_verified is True
    assert invitation.accepted_by == created_user
    assert response.data["created_user"] is True
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_accept_multi_role_invitation_creates_role_assignments(admin_user):
    _ensure_role_definition("SUPPORT_STAFF", "Support Staff")
    _ensure_role_definition("DEPARTMENT_HEAD", "Department Head")
    invitation = AdminRoleInvitation.objects.create(
        email="support.lead@test.com",
        role="SUPPORT_STAFF",
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    support_role = AdminInvitationRole.objects.get(code="SUPPORT_STAFF")
    department_head_role = AdminInvitationRole.objects.get(code="DEPARTMENT_HEAD")
    invitation.invitation_roles.create(
        role_definition=support_role,
        is_primary=False,
        permission_preset=support_role.permission_preset,
    )
    invitation.invitation_roles.create(
        role_definition=department_head_role,
        is_primary=True,
        permission_preset=department_head_role.permission_preset,
    )

    response = APIClient().post(
        reverse("admin_management:role-invitation-accept"),
        {
            "token": invitation.token,
            "full_name": "Support Lead",
            "password": "secure-pass-123",
            "password_confirm": "secure-pass-123",
        },
        format="json",
    )

    assert response.status_code == 201
    created_user = User.objects.get(email="support.lead@test.com")
    assignments = AdminUserRoleAssignment.objects.filter(user=created_user)
    assert assignments.count() == 2
    assert created_user.role == "DEPARTMENT_HEAD"
    assert set(assignments.values_list("role_definition__code", flat=True)) == {
        "SUPPORT_STAFF",
        "DEPARTMENT_HEAD",
    }


@pytest.mark.django_db
def test_accept_role_invitation_updates_matching_authenticated_user(api_client, admin_user, user):
    invitation = AdminRoleInvitation.objects.create(
        email=user.email,
        role="MODERATOR",
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("admin_management:role-invitation-accept"),
        {
            "token": invitation.token,
        },
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    invitation.refresh_from_db()
    assert user.role == "MODERATOR"
    assert invitation.accepted_by == user
    assert response.data["created_user"] is False
    assert response.data["role_changed"] is True


@pytest.mark.django_db
def test_existing_user_must_login_to_accept_invitation(admin_user, user):
    invitation = AdminRoleInvitation.objects.create(
        email=user.email,
        role="MODERATOR",
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = APIClient().post(
        reverse("admin_management:role-invitation-accept"),
        {"token": invitation.token},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["requires_login"] is True
    assert user.email in response.data["message"]


@pytest.mark.django_db
def test_bulk_role_invitation_csv_text_creates_batch(admin_client, admin_user):
    _ensure_role_definition("STUDENT", "Student")
    _ensure_role_definition("SUPPORT_STAFF", "Support Staff")
    _ensure_role_definition("INSTRUCTOR", "Instructor")
    response = admin_client.post(
        reverse("admin_management:role-invitation-bulk"),
        {
            "csv_text": (
                "email,roles,note,expires_in_days\n"
                "student.bulk@test.com,STUDENT,Welcome,7\n"
                "staff.bulk@test.com,SUPPORT_STAFF|INSTRUCTOR,Operations,14\n"
            ),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["summary"]["created"] == 2
    assert response.data["summary"]["failed"] == 0
    assert AdminInvitationBatch.objects.count() == 1
    assert AdminRoleInvitation.objects.filter(batch__isnull=False).count() == 2
