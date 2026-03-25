"""Services for admin management operations."""

import csv
from collections import OrderedDict
from datetime import timedelta
from io import StringIO
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Count, Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.accounts.authentication import generate_tokens_for_user
from apps.accounts.models import User
from apps.admin_management.models import (
    AdminInvitationBatch,
    AdminInvitationRole,
    AdminRoleInvitation,
    AdminRoleInvitationRole,
    AdminUserRoleAssignment,
)
from apps.announcements.models import Announcement
from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
from apps.core.emails import EmailService
from apps.courses.models import Course, Unit
from apps.downloads.models import Download
from apps.faculties.models import Department, Faculty
from apps.favorites.models import Favorite
from apps.moderation.models import AdminActivityLog
from apps.moderation.services import ModerationService
from apps.notifications.services import NotificationService
from apps.ratings.models import Rating
from apps.reports.models import Report
from apps.resources.models import Resource


def _user_display_name(user):
    """Return safe user display name."""
    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    combined = f"{first_name} {last_name}".strip()
    if combined:
        return combined
    full_name = getattr(user, "full_name", "") or ""
    if full_name:
        return full_name
    return getattr(user, "email", "")


def log_admin_activity(
    *,
    admin: User | None,
    action: str,
    target_type: str,
    target_id,
    target_title: str = "",
    metadata: dict | None = None,
):
    """Persist admin activity when an authenticated actor is available."""
    if not admin or not getattr(admin, "is_authenticated", False):
        return None

    return AdminActivityLog.objects.create(
        admin=admin,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        target_title=target_title or "",
        metadata=metadata or {},
    )


def get_admin_dashboard_data():
    """Aggregate high-level admin dashboard metrics."""
    seven_days_ago = timezone.now() - timedelta(days=7)

    users = {
        "total": User.objects.count(),
        "active": User.objects.filter(is_active=True).count(),
        "verified": User.objects.filter(is_verified=True).count(),
        "students": User.objects.filter(role__iexact="student").count(),
        "instructors": User.objects.filter(role__iexact="instructor").count(),
        "department_heads": User.objects.filter(role__iexact="department_head").count(),
        "support_staff": User.objects.filter(role__iexact="support_staff").count(),
        "moderators": User.objects.filter(role__iexact="moderator").count(),
        "admins": User.objects.filter(
            Q(role__iexact="admin") | Q(is_superuser=True)
        ).count(),
        "joined_last_7_days": User.objects.filter(
            date_joined__gte=seven_days_ago
        ).count(),
    }

    resources = {
        "total": Resource.objects.count(),
        "pending": Resource.objects.filter(status__in=["pending", "flagged"]).count(),
        "approved": Resource.objects.filter(status="approved").count(),
        "rejected": Resource.objects.filter(status="rejected").count(),
        "uploaded_last_7_days": Resource.objects.filter(
            created_at__gte=seven_days_ago
        ).count(),
    }

    reports = {
        "total": Report.objects.count(),
        "open": Report.objects.filter(status="open").count(),
        "in_review": Report.objects.filter(status="in_review").count(),
        "resolved": Report.objects.filter(status="resolved").count(),
        "dismissed": Report.objects.filter(status="dismissed").count(),
    }

    engagement = {
        "downloads": Download.objects.count(),
        "bookmarks": Bookmark.objects.count(),
        "favorites": Favorite.objects.count(),
        "comments": Comment.objects.count(),
        "ratings": Rating.objects.count(),
    }

    moderation = {
        "pending_resources": resources["pending"],
        "open_reports": reports["open"],
        "in_review_reports": reports["in_review"],
    }

    recent_resources = [
        {
            "id": str(resource.id),
            "title": resource.title,
            "status": resource.status,
            "uploaded_by_name": _user_display_name(resource.uploaded_by),
            "created_at": resource.created_at,
        }
        for resource in Resource.objects.select_related("uploaded_by").order_by(
            "-created_at"
        )[:5]
    ]

    recent_reports = [
        {
            "id": str(report.id),
            "target_type": report.get_target_type(),
            "target_title": report.get_target_title(),
            "reason_type": report.reason_type,
            "status": report.status,
            "created_at": report.created_at,
        }
        for report in Report.objects.select_related(
            "resource", "comment", "comment__user"
        ).order_by("-created_at")[:5]
    ]

    return {
        "users": users,
        "resources": resources,
        "reports": reports,
        "engagement": engagement,
        "moderation": moderation,
        "recent_resources": recent_resources,
        "recent_reports": recent_reports,
    }


def get_user_management_stats():
    """Get breakdown of users by role and account state."""
    total = User.objects.count()
    by_role = list(
        User.objects.values("role").annotate(count=Count("id")).order_by("role")
    )
    by_status = {
        "active": User.objects.filter(is_active=True).count(),
        "inactive": User.objects.filter(is_active=False).count(),
        "verified": User.objects.filter(is_verified=True).count(),
        "unverified": User.objects.filter(is_verified=False).count(),
    }

    return {
        "total": total,
        "by_role": by_role,
        "by_status": by_status,
    }


def get_resource_management_stats():
    """Get resource moderation and quality stats."""
    by_status = list(
        Resource.objects.values("status").annotate(count=Count("id")).order_by("status")
    )
    by_type = list(
        Resource.objects.values("resource_type")
        .annotate(count=Count("id"))
        .order_by("resource_type")
    )

    most_reported = list(
        Resource.objects.annotate(report_count=Count("reports"))
        .filter(report_count__gt=0)
        .order_by("-report_count", "-created_at")
        .values(
            "id", "title", "status", "report_count", "download_count", "view_count"
        )[:10]
    )

    return {
        "by_status": by_status,
        "by_type": by_type,
        "most_reported": most_reported,
    }


def get_academic_stats():
    """Get current academic structure counts."""
    return {
        "faculties": Faculty.objects.count(),
        "departments": Department.objects.count(),
        "courses": Course.objects.count(),
        "units": Unit.objects.count(),
    }


ROLE_INVITATION_EXPIRY_DAYS = 7
ROLE_PRIORITY = {
    "ADMIN": 0,
    "DEPARTMENT_HEAD": 1,
    "MODERATOR": 2,
    "INSTRUCTOR": 3,
    "SUPPORT_STAFF": 4,
    "STUDENT": 5,
}
DEFAULT_ROLE_INVITATION_SUBJECT = "CampusHub invitation for {primary_role_name}"
DEFAULT_ROLE_INVITATION_BODY = (
    "Hello,\n\n"
    "You've been invited to join {site_name} with the following roles: {role_names_csv}.\n\n"
    "Invited by: {invited_by_name}\n"
    "Invitation email: {invitee_email}\n"
    "{note_block}"
    "Accept invitation: {landing_url}\n"
    "{app_url_block}"
    "This invitation expires on {expires_at}.\n"
)


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_role_code(value: str) -> str:
    return str(value or "").strip().upper()


def _dedupe_keep_order(values):
    unique_values = OrderedDict()
    for value in values:
        if value:
            unique_values[value] = True
    return list(unique_values.keys())


def _split_role_values(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        raw_values = value
    else:
        raw_values = str(value or "").replace("|", ",").replace(";", ",").split(",")
    return _dedupe_keep_order(_normalize_role_code(item) for item in raw_values if str(item).strip())


def _get_role_priority(role_code: str) -> int:
    return ROLE_PRIORITY.get(_normalize_role_code(role_code), len(ROLE_PRIORITY) + 10)


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + str(key) + "}"


def _format_template(template: str, context: dict) -> str:
    return str(template or "").format_map(_SafeFormatDict(context)).strip()


def _get_invitation_roles_queryset(*, include_inactive: bool = False):
    queryset = AdminInvitationRole.objects.all().order_by("sort_order", "name")
    if include_inactive:
        return queryset
    return queryset.filter(is_active=True, is_assignable=True)


def actor_can_invite_role(actor: User | None, role_definition: AdminInvitationRole) -> bool:
    """Check whether the actor may invite the supplied role definition."""
    if not actor or not getattr(actor, "is_authenticated", False):
        return False
    if getattr(actor, "is_superuser", False):
        return True
    if not getattr(actor, "is_admin", False):
        return False
    if str(role_definition.code or "").upper() == "ADMIN":
        return False
    if role_definition.requires_superuser:
        return False

    required_permissions = [
        str(permission_code).strip()
        for permission_code in (role_definition.inviter_permissions or [])
        if str(permission_code).strip()
    ]
    return not required_permissions or actor.has_perms(required_permissions)


def get_available_invitation_roles(*, actor: User | None, include_inactive: bool = False):
    """Return role definitions annotated with invite eligibility for the actor."""
    role_definitions = list(
        _get_invitation_roles_queryset(include_inactive=include_inactive)
    )
    return [
        {
            "role_definition": role_definition,
            "can_invite": actor_can_invite_role(actor, role_definition),
        }
        for role_definition in role_definitions
    ]


def _resolve_role_definitions_for_actor(
    *,
    actor: User | None,
    role_codes,
    validate_permissions: bool = True,
) -> list[AdminInvitationRole]:
    requested_codes = _split_role_values(role_codes)
    if not requested_codes:
        raise ValueError("Select at least one role for the invitation.")

    role_map = {
        role_definition.code: role_definition
        for role_definition in _get_invitation_roles_queryset().filter(
            code__in=requested_codes
        )
    }
    missing_codes = [code for code in requested_codes if code not in role_map]
    if missing_codes:
        missing_display = ", ".join(sorted(missing_codes))
        raise ValueError(f"Unknown or inactive roles: {missing_display}.")

    role_definitions = [role_map[code] for code in requested_codes]
    if validate_permissions:
        forbidden_roles = [
            role_definition.name
            for role_definition in role_definitions
            if not actor_can_invite_role(actor, role_definition)
        ]
        if forbidden_roles:
            forbidden_display = ", ".join(forbidden_roles)
            raise PermissionError(
                f"You do not have permission to invite the selected roles: {forbidden_display}."
            )
    return role_definitions


def _select_primary_role_definition(role_definitions: list[AdminInvitationRole]) -> AdminInvitationRole:
    return sorted(
        role_definitions,
        key=lambda role_definition: (
            _get_role_priority(role_definition.code),
            role_definition.sort_order,
            role_definition.name,
        ),
    )[0]


def get_invitation_role_definitions_for_invitation(
    invitation: AdminRoleInvitation,
) -> list[AdminInvitationRole]:
    """Return the effective role definitions attached to an invitation."""
    assignments = invitation.get_role_assignments()
    if assignments:
        return [
            assignment.role_definition
            for assignment in assignments
            if assignment.role_definition_id
        ]
    fallback_role = (
        AdminInvitationRole.objects.filter(code__iexact=invitation.role).first()
    )
    return [fallback_role] if fallback_role else []


def _build_role_invitation_context(
    invitation: AdminRoleInvitation,
    role_definitions: list[AdminInvitationRole],
    request=None,
) -> dict:
    primary_role = (
        _select_primary_role_definition(role_definitions)
        if role_definitions
        else AdminInvitationRole(
            code=invitation.role,
            name=invitation.get_role_display(),
            sort_order=999,
        )
    )
    landing_url = build_role_invitation_landing_url(request, invitation.token)
    app_url = build_role_invitation_client_url(invitation.token)
    invited_by_name = _user_display_name(invitation.invited_by) or "CampusHub admin"
    role_names = [role_definition.name for role_definition in role_definitions] or [
        invitation.get_role_display()
    ]
    role_codes = [role_definition.code for role_definition in role_definitions] or [
        invitation.role
    ]
    note = invitation.note or ""

    context = {
        "site_name": getattr(settings, "SITE_NAME", "CampusHub"),
        "invitee_email": invitation.email,
        "invited_by_name": invited_by_name,
        "role_names_csv": ", ".join(role_names),
        "role_codes_csv": ", ".join(role_codes),
        "primary_role_name": primary_role.name,
        "primary_role_code": primary_role.code,
        "roles_count": len(role_names),
        "note": note,
        "note_block": f"Note: {note}\n" if note else "",
        "landing_url": landing_url,
        "accept_url": landing_url,
        "app_url": app_url,
        "app_url_block": (
            f"Open directly in app: {app_url}\n"
            if app_url and app_url != landing_url
            else ""
        ),
        "expires_at": invitation.expires_at.strftime("%Y-%m-%d %H:%M %Z"),
        "expires_at_iso": invitation.expires_at.isoformat(),
    }
    if invitation.metadata:
        context.update(
            {
                f"metadata_{key}": value
                for key, value in invitation.metadata.items()
                if isinstance(key, str)
            }
        )
    return context


def render_role_invitation_email(
    *,
    invitation: AdminRoleInvitation,
    role_definitions: list[AdminInvitationRole],
    request=None,
) -> tuple[str, str]:
    """Render the invitation subject/body from role defaults or invitation snapshots."""
    primary_role = (
        _select_primary_role_definition(role_definitions)
        if role_definitions
        else None
    )
    subject_template = (
        invitation.email_subject
        or getattr(primary_role, "email_subject_template", "")
        or DEFAULT_ROLE_INVITATION_SUBJECT
    )
    body_template = (
        invitation.email_body
        or getattr(primary_role, "email_body_template", "")
        or DEFAULT_ROLE_INVITATION_BODY
    )
    context = _build_role_invitation_context(invitation, role_definitions, request=request)
    subject = _format_template(subject_template, context)
    body = _format_template(body_template, context)
    return subject, body


def _build_mobile_role_invite_link(token: str) -> str:
    scheme = str(getattr(settings, "MOBILE_DEEPLINK_SCHEME", "") or "").strip()
    if not scheme:
        return ""
    query = urlencode({"token": token})
    return f"{scheme}://role-invite?{query}" if query else f"{scheme}://role-invite"


def build_role_invitation_landing_url(request, token: str) -> str:
    """Build the canonical shareable role-invite landing URL."""
    try:
        path = reverse("role-invitation-landing", args=[token])
    except NoReverseMatch:
        path = f"/role-invite/{token}/"
    if request is not None:
        return request.build_absolute_uri(path)

    frontend_base = (
        str(getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
        or str(getattr(settings, "RESOURCE_SHARE_BASE_URL", "") or "").rstrip("/")
        or str(getattr(settings, "WEB_APP_URL", "") or "").rstrip("/")
    )
    return f"{frontend_base}{path}" if frontend_base else path


def build_role_invitation_client_url(token: str) -> str:
    """Build the preferred app/web destination for an invitation token."""
    frontend_base = (
        str(getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
        or str(getattr(settings, "RESOURCE_SHARE_BASE_URL", "") or "").rstrip("/")
        or str(getattr(settings, "WEB_APP_URL", "") or "").rstrip("/")
    )
    query = urlencode({"token": token})
    if frontend_base:
        return f"{frontend_base}/role-invite?{query}" if query else f"{frontend_base}/role-invite"
    return _build_mobile_role_invite_link(token)


def send_role_invitation_email(*, invitation: AdminRoleInvitation, request=None) -> bool:
    """Send an email with the role invitation link."""
    role_definitions = get_invitation_role_definitions_for_invitation(invitation)
    subject, body = render_role_invitation_email(
        invitation=invitation,
        role_definitions=role_definitions,
        request=request,
    )
    invitation.email_subject = subject
    invitation.email_body = body
    invitation.last_sent_at = timezone.now()
    invitation.save(
        update_fields=["email_subject", "email_body", "last_sent_at", "updated_at"]
    )
    sent = EmailService.send_email(
        subject=subject,
        message=body,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
    if sent:
        log_admin_activity(
            admin=invitation.invited_by,
            action="user_invitation_sent",
            target_type="role_invitation",
            target_id=invitation.id,
            target_title=invitation.email,
            metadata={
                "email": invitation.email,
                "roles": invitation.get_role_codes(),
                "source": invitation.source,
            },
        )
    return sent


def _active_role_invitation_queryset():
    return AdminRoleInvitation.objects.filter(
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )


def get_role_invitation_by_token(token: str) -> AdminRoleInvitation | None:
    return (
        AdminRoleInvitation.objects.select_related(
            "invited_by", "accepted_by", "revoked_by", "batch"
        )
        .prefetch_related("invitation_roles__role_definition")
        .filter(token=str(token or "").strip())
        .first()
    )


def validate_role_invitation_token(*, token: str, user: User | None = None) -> dict:
    """Return a user-facing validation payload for a role invite token."""
    invitation = get_role_invitation_by_token(token)
    if not invitation:
        return {"valid": False, "message": "This invitation link is invalid."}

    role_definitions = get_invitation_role_definitions_for_invitation(invitation)
    role_codes = invitation.get_role_codes()
    role_names = invitation.get_role_names()

    existing_user = User.objects.filter(email__iexact=invitation.email).first()
    if invitation.accepted_at:
        return {
            "valid": False,
            "status": "accepted",
            "message": "This invitation has already been used.",
        }
    if invitation.revoked_at:
        return {
            "valid": False,
            "status": "revoked",
            "message": "This invitation was revoked by an administrator.",
        }
    if invitation.expires_at <= timezone.now():
        return {
            "valid": False,
            "status": "expired",
            "message": "This invitation has expired.",
        }

    authenticated_user = user if user and getattr(user, "is_authenticated", False) else None
    invited_email = invitation.email
    invited_email_matches_session = bool(
        authenticated_user
        and _normalize_email(authenticated_user.email) == _normalize_email(invited_email)
    )

    can_accept = True
    message = "Invitation is ready to accept."
    if existing_user and not authenticated_user:
        can_accept = False
        message = f"Sign in with {invited_email} to accept this invitation."
    elif authenticated_user and not invited_email_matches_session:
        can_accept = False
        message = f"This invite is for {invited_email}. Sign in with that account to continue."

    return {
        "valid": True,
        "status": invitation.status,
        "message": message,
        "role": invitation.role,
        "roles": role_codes,
        "role_names": role_names,
        "email": invited_email,
        "note": invitation.note,
        "expires_at": invitation.expires_at,
        "metadata": invitation.metadata,
        "existing_account": bool(existing_user),
        "requires_login": bool(existing_user and not invited_email_matches_session),
        "can_accept": can_accept,
        "accept_url": build_role_invitation_landing_url(None, invitation.token),
        "app_url": build_role_invitation_client_url(invitation.token),
        "invited_by_name": _user_display_name(invitation.invited_by),
        "batch_id": str(invitation.batch_id) if invitation.batch_id else None,
        "email_subject": invitation.email_subject,
        "email_body": invitation.email_body,
        "role_details": [
            {
                "code": role_definition.code,
                "name": role_definition.name,
                "description": role_definition.description,
                "permission_preset": role_definition.permission_preset,
            }
            for role_definition in role_definitions
        ],
    }


def _group_name_for_role_definition(role_definition: AdminInvitationRole) -> str:
    return f"CampusHub Role::{role_definition.code}"


def _resolve_permission_queryset(permission_codes: list[str]):
    resolved_pairs = []
    for permission_code in permission_codes:
        normalized_code = str(permission_code or "").strip()
        if not normalized_code or "." not in normalized_code:
            continue
        app_label, codename = normalized_code.split(".", 1)
        resolved_pairs.append((app_label, codename))

    permissions = {}
    if resolved_pairs:
        queryset = Permission.objects.filter(
            content_type__app_label__in=[pair[0] for pair in resolved_pairs],
            codename__in=[pair[1] for pair in resolved_pairs],
        ).select_related("content_type")
        permissions = {
            f"{permission.content_type.app_label}.{permission.codename}": permission
            for permission in queryset
        }

    ordered_permissions = []
    missing_permissions = []
    for permission_code in permission_codes:
        permission = permissions.get(str(permission_code).strip())
        if permission:
            ordered_permissions.append(permission)
        else:
            missing_permissions.append(str(permission_code).strip())
    return ordered_permissions, missing_permissions


def sync_role_definition_group(role_definition: AdminInvitationRole):
    """Create or update the auth group mapped to a role definition."""
    group, _ = Group.objects.get_or_create(name=_group_name_for_role_definition(role_definition))
    resolved_permissions, missing_permissions = _resolve_permission_queryset(
        list(role_definition.permission_preset or [])
    )
    group.permissions.set(resolved_permissions)
    return {
        "group": group,
        "applied_permissions": [
            f"{permission.content_type.app_label}.{permission.codename}"
            for permission in resolved_permissions
        ],
        "missing_permissions": missing_permissions,
    }


def _determine_effective_primary_role(
    *, current_role: str | None, invited_role_definitions: list[AdminInvitationRole]
) -> str:
    invited_primary = _select_primary_role_definition(invited_role_definitions).code
    normalized_current_role = _normalize_role_code(current_role)
    if not normalized_current_role:
        return invited_primary
    if _get_role_priority(normalized_current_role) <= _get_role_priority(invited_primary):
        return normalized_current_role
    return invited_primary


def _sync_user_role_assignments(
    *,
    user: User,
    role_definitions: list[AdminInvitationRole],
    invitation: AdminRoleInvitation | None,
    assigned_by: User | None,
    primary_role_code: str,
):
    applied_roles = []
    applied_permissions = []
    missing_permissions = []

    role_definitions_by_code = {
        role_definition.code: role_definition for role_definition in role_definitions
    }
    if primary_role_code not in role_definitions_by_code:
        primary_role_definition = AdminInvitationRole.objects.filter(
            code=primary_role_code
        ).first()
        if primary_role_definition:
            role_definitions_by_code[primary_role_code] = primary_role_definition

    for role_definition in role_definitions_by_code.values():
        group_result = sync_role_definition_group(role_definition)
        user.groups.add(group_result["group"])
        assignment_defaults = {
            "invitation": invitation,
            "assigned_by": assigned_by,
            "is_primary": role_definition.code == primary_role_code,
            "permission_preset": list(role_definition.permission_preset or []),
            "metadata": {
                "group_name": group_result["group"].name,
                "applied_permissions": group_result["applied_permissions"],
            },
            "revoked_at": None,
        }
        AdminUserRoleAssignment.objects.update_or_create(
            user=user,
            role_definition=role_definition,
            defaults=assignment_defaults,
        )
        applied_roles.append(role_definition.code)
        applied_permissions.extend(group_result["applied_permissions"])
        missing_permissions.extend(group_result["missing_permissions"])

    AdminUserRoleAssignment.objects.filter(user=user).exclude(
        role_definition__code=primary_role_code
    ).update(is_primary=False)
    return {
        "applied_roles": _dedupe_keep_order(applied_roles),
        "applied_permissions": _dedupe_keep_order(applied_permissions),
        "missing_permissions": _dedupe_keep_order(missing_permissions),
    }


def create_role_invitation(
    *,
    actor: User,
    email: str,
    role: str | None = None,
    roles=None,
    note: str = "",
    expires_in_days: int = ROLE_INVITATION_EXPIRY_DAYS,
    expires_at=None,
    metadata: dict | None = None,
    source: str = AdminRoleInvitation.InvitationSource.API,
    batch: AdminInvitationBatch | None = None,
    email_subject: str = "",
    email_body: str = "",
    request=None,
) -> AdminRoleInvitation:
    """Create and email a new role-based admin invitation."""
    normalized_email = _normalize_email(email)
    role_definitions = _resolve_role_definitions_for_actor(
        actor=actor,
        role_codes=roles or [role],
    )
    primary_role = _select_primary_role_definition(role_definitions)
    expiration = expires_at or (
        timezone.now()
        + timedelta(days=max(1, int(expires_in_days or ROLE_INVITATION_EXPIRY_DAYS)))
    )
    invitation_metadata = dict(metadata or {})
    invitation_metadata.setdefault(
        "requested_roles", [role_definition.code for role_definition in role_definitions]
    )

    with transaction.atomic():
        _active_role_invitation_queryset().filter(email__iexact=normalized_email).update(
            revoked_at=timezone.now(),
            revoked_by=actor,
            updated_at=timezone.now(),
        )

        invitation = AdminRoleInvitation.objects.create(
            email=normalized_email,
            role=primary_role.code,
            note=note or "",
            source=source,
            metadata=invitation_metadata,
            email_subject=email_subject or "",
            email_body=email_body or "",
            invited_by=actor,
            batch=batch,
            expires_at=expiration,
        )
        AdminRoleInvitationRole.objects.bulk_create(
            [
                AdminRoleInvitationRole(
                    invitation=invitation,
                    role_definition=role_definition,
                    is_primary=role_definition.code == primary_role.code,
                    permission_preset=list(role_definition.permission_preset or []),
                )
                for role_definition in role_definitions
            ]
        )

    send_role_invitation_email(invitation=invitation, request=request)
    log_admin_activity(
        admin=actor,
        action="user_invitation_created",
        target_type="role_invitation",
        target_id=invitation.id,
        target_title=normalized_email,
        metadata={
            "email": normalized_email,
            "role": primary_role.code,
            "roles": [role_definition.code for role_definition in role_definitions],
            "expires_at": invitation.expires_at.isoformat(),
            "source": source,
            "batch_id": str(batch.id) if batch else None,
        },
    )
    return invitation


def create_role_invitation_batch(
    *,
    actor: User,
    csv_file=None,
    csv_text: str = "",
    default_roles=None,
    default_note: str = "",
    default_expires_in_days: int = ROLE_INVITATION_EXPIRY_DAYS,
    request=None,
):
    """Create invitations in bulk from a CSV upload."""
    file_name = getattr(csv_file, "name", "") or "invitations.csv"
    if csv_file is not None:
        try:
            decoded_rows = csv_file.read().decode("utf-8-sig")
        except Exception as exc:
            raise ValueError("CSV upload must be UTF-8 encoded.") from exc
    else:
        decoded_rows = str(csv_text or "").strip()
        file_name = "invitations.csv"

    if not decoded_rows:
        raise ValueError("CSV content cannot be empty.")

    reader = csv.DictReader(StringIO(decoded_rows))
    if "email" not in (reader.fieldnames or []):
        raise ValueError("CSV upload must contain an 'email' column.")

    batch = AdminInvitationBatch.objects.create(
        name=f"Bulk invitation upload {timezone.now():%Y-%m-%d %H:%M}",
        source_file_name=file_name,
        invited_by=actor,
        metadata={"default_roles": _split_role_values(default_roles or [])},
    )

    created_invitations = []
    errors = []
    total_rows = 0
    for row_number, row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        total_rows += 1
        row_email = _normalize_email(row.get("email"))
        if not row_email:
            errors.append({"row": row_number, "email": "", "error": "Email is required."})
            continue
        row_roles = _split_role_values(row.get("roles") or row.get("role") or default_roles or [])
        row_note = str(row.get("note") or default_note or "").strip()
        row_expiry = row.get("expires_in_days") or default_expires_in_days
        row_metadata = {
            key: value
            for key, value in row.items()
            if key not in {"email", "roles", "role", "note", "expires_in_days"}
            and str(value or "").strip()
        }
        row_metadata["csv_row"] = row_number

        try:
            invitation = create_role_invitation(
                actor=actor,
                email=row_email,
                roles=row_roles,
                note=row_note,
                expires_in_days=int(row_expiry or default_expires_in_days),
                metadata=row_metadata,
                source=AdminRoleInvitation.InvitationSource.CSV,
                batch=batch,
                request=request,
            )
            created_invitations.append(invitation)
        except Exception as exc:
            errors.append(
                {
                    "row": row_number,
                    "email": row_email,
                    "error": str(exc),
                }
            )

    batch.total_rows = total_rows
    batch.successful_rows = len(created_invitations)
    batch.failed_rows = len(errors)
    batch.metadata = {
        **(batch.metadata or {}),
        "errors": errors,
    }
    batch.save(
        update_fields=[
            "total_rows",
            "successful_rows",
            "failed_rows",
            "metadata",
            "updated_at",
        ]
    )

    log_admin_activity(
        admin=actor,
        action="user_invitation_batch_created",
        target_type="role_invitation_batch",
        target_id=batch.id,
        target_title=batch.name,
        metadata={
            "source_file_name": file_name,
            "total_rows": total_rows,
            "successful_rows": len(created_invitations),
            "failed_rows": len(errors),
        },
    )
    return {
        "batch": batch,
        "created_invitations": created_invitations,
        "errors": errors,
    }


def revoke_role_invitation(*, actor: User, invitation: AdminRoleInvitation) -> dict:
    """Revoke a still-pending role invitation."""
    if invitation.accepted_at:
        return {"success": False, "message": "Accepted invitations cannot be revoked."}
    if invitation.revoked_at:
        return {"success": True, "message": "Invitation is already revoked."}
    if invitation.expires_at <= timezone.now():
        return {"success": False, "message": "Expired invitations cannot be revoked."}

    invitation.revoked_at = timezone.now()
    invitation.revoked_by = actor
    invitation.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    log_admin_activity(
        admin=actor,
        action="user_invitation_revoked",
        target_type="role_invitation",
        target_id=invitation.id,
        target_title=invitation.email,
        metadata={"email": invitation.email, "roles": invitation.get_role_codes()},
    )
    return {"success": True, "message": "Invitation revoked successfully."}


@transaction.atomic
def accept_role_invitation(
    *,
    invitation: AdminRoleInvitation,
    actor: User | None = None,
    full_name: str = "",
    password: str = "",
    registration_number: str = "",
    phone_number: str = "",
):
    """Accept an invitation by creating or updating the invited account."""
    validation = validate_role_invitation_token(token=invitation.token, user=actor)
    if not validation.get("valid"):
        return {"success": False, "message": validation["message"], "status": validation.get("status")}

    role_definitions = get_invitation_role_definitions_for_invitation(invitation)
    if not role_definitions:
        return {
            "success": False,
            "message": "This invitation has no active roles attached to it.",
        }

    existing_user = User.objects.filter(email__iexact=invitation.email).first()
    authenticated_user = actor if actor and getattr(actor, "is_authenticated", False) else None

    if existing_user and not authenticated_user:
        return {
            "success": False,
            "message": validation["message"],
            "requires_login": True,
            "email": invitation.email,
        }

    if authenticated_user and _normalize_email(authenticated_user.email) != _normalize_email(invitation.email):
        return {
            "success": False,
            "message": validation["message"],
            "requires_login": True,
            "email": invitation.email,
            "forbidden": True,
        }

    created_user = False
    tokens = None
    if authenticated_user:
        user = authenticated_user
    else:
        if not full_name.strip():
            return {"success": False, "message": "Full name is required to create the invited account."}
        if not password:
            return {"success": False, "message": "Password is required to create the invited account."}
        user = User.objects.create_user(
            email=invitation.email,
            password=password,
            full_name=full_name.strip(),
            registration_number=registration_number or None,
            phone_number=phone_number or "",
            role=invitation.role,
            is_active=True,
            is_verified=True,
        )
        created_user = True
        tokens = generate_tokens_for_user(user)

    previous_role = user.role
    effective_primary_role = _determine_effective_primary_role(
        current_role=user.role,
        invited_role_definitions=role_definitions,
    )
    fields_to_update = []
    if user.role != effective_primary_role:
        user.role = effective_primary_role
        fields_to_update.append("role")
    if not user.is_verified:
        user.is_verified = True
        fields_to_update.append("is_verified")
    if fields_to_update:
        user.save(update_fields=[*fields_to_update, "updated_at"])

    role_assignment_result = _sync_user_role_assignments(
        user=user,
        role_definitions=role_definitions,
        invitation=invitation,
        assigned_by=invitation.invited_by,
        primary_role_code=effective_primary_role,
    )

    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.accepted_metadata = {
        "accepted_by_user_id": user.id,
        "created_user": created_user,
        "applied_roles": role_assignment_result["applied_roles"],
        "applied_permissions": role_assignment_result["applied_permissions"],
        "missing_permissions": role_assignment_result["missing_permissions"],
    }
    invitation.save(
        update_fields=["accepted_by", "accepted_at", "accepted_metadata", "updated_at"]
    )

    log_admin_activity(
        admin=invitation.invited_by,
        action="user_invitation_accepted",
        target_type="role_invitation",
        target_id=invitation.id,
        target_title=invitation.email,
        metadata={
            "accepted_by_user_id": user.id,
            "email": invitation.email,
            "previous_role": previous_role,
            "new_role": effective_primary_role,
            "roles": role_assignment_result["applied_roles"],
            "created_user": created_user,
        },
    )

    return {
        "success": True,
        "message": "Invitation accepted successfully.",
        "user": user,
        "invitation": invitation,
        "created_user": created_user,
        "role_changed": previous_role != effective_primary_role,
        "applied_roles": role_assignment_result["applied_roles"],
        "applied_permissions": role_assignment_result["applied_permissions"],
        "missing_permissions": role_assignment_result["missing_permissions"],
        "tokens": tokens,
    }


def update_user_status(*, actor: User, target: User, is_active: bool):
    """Activate or deactivate a user with guardrails."""
    if actor.id == target.id and not is_active:
        return {
            "success": False,
            "message": "You cannot deactivate your own account from this endpoint.",
        }

    if target.is_superuser and not actor.is_superuser:
        return {
            "success": False,
            "message": "Only a superuser can change another superuser status.",
        }

    if target.is_active == is_active:
        state = "active" if is_active else "inactive"
        return {"success": True, "message": f"User is already {state}."}

    target.is_active = is_active
    target.save(update_fields=["is_active", "updated_at"])
    state = "activated" if is_active else "deactivated"
    log_admin_activity(
        admin=actor,
        action="user_activated" if is_active else "user_suspended",
        target_type="user",
        target_id=target.id,
        target_title=_user_display_name(target),
        metadata={"email": target.email, "is_active": is_active},
    )
    return {"success": True, "message": f"User {target.email} {state} successfully."}


def update_user_role(*, actor: User, target: User, role: str):
    """Update user role with superuser protection."""
    normalized_role = str(role).upper()
    previous_role = target.role

    if target.is_superuser and not actor.is_superuser:
        return {
            "success": False,
            "message": "Only a superuser can change another superuser role.",
        }

    if target.role == normalized_role:
        return {
            "success": True,
            "message": f"User already has role {normalized_role}.",
        }

    target.role = normalized_role
    target.save(update_fields=["role", "updated_at"])
    role_definition = AdminInvitationRole.objects.filter(code=normalized_role).first()
    if role_definition:
        group_result = sync_role_definition_group(role_definition)
        target.groups.add(group_result["group"])
        AdminUserRoleAssignment.objects.update_or_create(
            user=target,
            role_definition=role_definition,
            defaults={
                "assigned_by": actor,
                "is_primary": True,
                "permission_preset": list(role_definition.permission_preset or []),
                "metadata": {
                    "source": "manual_role_update",
                    "applied_permissions": group_result["applied_permissions"],
                },
                "revoked_at": None,
            },
        )
        AdminUserRoleAssignment.objects.filter(user=target).exclude(
            role_definition=role_definition
        ).update(is_primary=False)
    log_admin_activity(
        admin=actor,
        action="user_role_updated",
        target_type="user",
        target_id=target.id,
        target_title=_user_display_name(target),
        metadata={
            "email": target.email,
            "previous_role": previous_role,
            "new_role": normalized_role,
        },
    )
    return {
        "success": True,
        "message": f"User role updated to {normalized_role}.",
    }


def review_resource(
    *, resource: Resource, reviewer: User, approve: bool, reason: str = ""
):
    """Approve or reject resource via central moderation service."""
    if approve:
        return ModerationService.approve_resource(
            resource=resource,
            reviewer=reviewer,
            reason=reason,
        )
    return ModerationService.reject_resource(
        resource=resource,
        reviewer=reviewer,
        reason=reason,
    )


def delete_resource(*, resource: Resource, actor: User | None = None):
    """Delete a resource and associated file safely."""
    title = resource.title
    resource_id = resource.id
    uploaded_by_id = resource.uploaded_by_id
    if resource.file:
        resource.file.delete(save=False)
    resource.delete()
    log_admin_activity(
        admin=actor,
        action="resource_deleted",
        target_type="resource",
        target_id=resource_id,
        target_title=title,
        metadata={"uploaded_by_id": uploaded_by_id},
    )
    return {
        "success": True,
        "message": f'Resource "{title}" deleted successfully.',
    }


@transaction.atomic
def update_report_status(
    *, report: Report, reviewer: User, status: str, resolution_note: str = ""
):
    """Update report status and trigger moderation side effects."""
    previous_status = report.status
    report.status = status
    report.reviewed_by = reviewer
    report.resolution_note = resolution_note
    report.save(
        update_fields=["status", "reviewed_by", "resolution_note", "updated_at"]
    )

    if report.status != previous_status and report.status in [
        "in_review",
        "resolved",
        "dismissed",
    ]:
        NotificationService.notify_report_status(report)
    if status in ["resolved", "dismissed"]:
        log_admin_activity(
            admin=reviewer,
            action="report_resolved" if status == "resolved" else "report_dismissed",
            target_type="report",
            target_id=report.id,
            target_title=report.get_target_title(),
            metadata={
                "previous_status": previous_status,
                "new_status": status,
                "reason_type": report.reason_type,
            },
        )
        ModerationService.maybe_release_comment_after_report_decision(report)

    return report


def can_manage_target_user(*, actor: User, target: User) -> bool:
    """Check if actor can manage target user account."""
    if not actor.is_authenticated or not actor.is_admin:
        return False
    if target.is_superuser and not actor.is_superuser:
        return False
    return True


def get_moderation_queues():
    """Return automatically held resources and open reports counts."""
    return {
        "pending_resources": Resource.objects.filter(
            status__in=["pending", "flagged"]
        ).count(),
        "open_reports": Report.objects.filter(status="open").count(),
        "in_review_reports": Report.objects.filter(status="in_review").count(),
    }


def announcement_lifecycle_action(
    *, announcement: Announcement, action: str, actor: User | None = None
):
    """Apply lifecycle actions to announcement state."""
    from apps.announcements.models import AnnouncementStatus

    previous_status = announcement.status
    if action == "publish":
        announcement.status = AnnouncementStatus.PUBLISHED
        if not announcement.published_at:
            announcement.published_at = timezone.now()
    elif action == "archive":
        announcement.status = AnnouncementStatus.ARCHIVED
    elif action == "unpublish":
        announcement.status = AnnouncementStatus.DRAFT
        announcement.published_at = None
    announcement.save(update_fields=["status", "published_at", "updated_at"])

    if action in {"publish", "archive"}:
        log_admin_activity(
            admin=actor,
            action=(
                "announcement_published"
                if action == "publish"
                else "announcement_archived"
            ),
            target_type="announcement",
            target_id=announcement.id,
            target_title=announcement.title,
            metadata={
                "previous_status": previous_status,
                "new_status": announcement.status,
            },
        )
    return announcement


def admin_global_search(query: str, limit: int = 20):
    """
    Perform global search across the platform for admin purposes.
    Searches users, resources, reports, courses, faculties, departments, and units.
    """
    from apps.accounts.models import User
    from apps.courses.models import Course, Unit
    from apps.faculties.models import Department, Faculty
    from apps.reports.models import Report
    from apps.resources.models import Resource

    results = {
        "users": [],
        "resources": [],
        "reports": [],
        "faculties": [],
        "departments": [],
        "courses": [],
        "units": [],
    }

    if not query or len(query) < 2:
        return results

    # Search users
    users = User.objects.filter(
        Q(email__icontains=query)
        | Q(full_name__icontains=query)
        | Q(registration_number__icontains=query)
    )[:limit]
    results["users"] = [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
        }
        for u in users
    ]

    # Search resources
    resources = Resource.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query)
    )[:limit]
    results["resources"] = [
        {
            "id": str(r.id),
            "title": r.title,
            "status": r.status,
            "resource_type": r.resource_type,
            "uploaded_by": r.uploaded_by.email if r.uploaded_by else None,
        }
        for r in resources
    ]

    # Search reports
    reports = Report.objects.filter(
        Q(message__icontains=query)
    )[:limit]
    results["reports"] = [
        {
            "id": str(r.id),
            "reason_type": r.reason_type,
            "status": r.status,
            "reporter": r.reporter.email if r.reporter else None,
        }
        for r in reports
    ]

    # Search faculties
    faculties = Faculty.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query)
    )[:limit]
    results["faculties"] = [
        {
            "id": str(f.id),
            "name": f.name,
            "code": f.code,
        }
        for f in faculties
    ]

    # Search departments
    departments = Department.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query)
    )[:limit]
    results["departments"] = [
        {
            "id": str(d.id),
            "name": d.name,
            "code": d.code,
            "faculty": d.faculty.name if d.faculty else None,
        }
        for d in departments
    ]

    # Search courses
    courses = Course.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query)
    )[:limit]
    results["courses"] = [
        {
            "id": str(c.id),
            "name": c.name,
            "code": c.code,
        }
        for c in courses
    ]

    # Search units
    units = Unit.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query)
    )[:limit]
    results["units"] = [
        {
            "id": str(u.id),
            "name": u.name,
            "code": u.code,
        }
        for u in units
    ]

    return results


def get_system_health():
    """
    Get system health and storage metrics.
    """
    from django.db import connection
    from django.utils import timezone
    from datetime import timedelta
    import os

    # Database health
    db_health = {"healthy": True, "error": None}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        db_health = {"healthy": False, "error": str(e)}

    # Storage metrics
    storage = {"total_files": 0, "total_size_bytes": 0}
    try:
        from apps.resources.models import Resource
        resources_with_files = Resource.objects.exclude(file="").exclude(file__isnull=True)
        storage["total_files"] = resources_with_files.count()
        storage["total_size_bytes"] = sum(
            r.file_size for r in resources_with_files.iterator() if r.file_size
        )
        storage["total_size_mb"] = round(storage["total_size_bytes"] / (1024 * 1024), 2)
        storage["total_size_gb"] = round(storage["total_size_bytes"] / (1024 * 1024 * 1024), 2)

        # Average file size
        if storage["total_files"] > 0:
            storage["average_size_mb"] = round(
                storage["total_size_bytes"] / storage["total_files"] / (1024 * 1024), 2
            )

        # Largest resources
        largest = resources_with_files.order_by("-file_size")[:5]
        storage["largest_resources"] = [
            {
                "id": str(r.id),
                "title": r.title,
                "size_mb": round(r.file_size / (1024 * 1024), 2) if r.file_size else 0,
            }
            for r in largest if r.file_size
        ]
    except Exception as e:
        storage["error"] = str(e)

    # API uptime (approximate)
    api_health = {"status": "running"}

    # Error rates (approximate - check recent errors)
    error_rates = {"errors_last_24h": 0}
    try:
        from apps.core.api_logging import APILog
        since = timezone.now() - timedelta(hours=24)
        error_rates["errors_last_24h"] = APILog.objects.filter(
            created_at__gte=since,
            status_code__gte=500
        ).count()
    except Exception:
        pass

    # Active users
    active_users = {"last_24h": 0, "last_7_days": 0, "last_30_days": 0}
    try:
        from apps.accounts.models import User
        now = timezone.now()
        active_users["last_24h"] = User.objects.filter(
            last_login__gte=now - timedelta(hours=24)
        ).count()
        active_users["last_7_days"] = User.objects.filter(
            last_login__gte=now - timedelta(days=7)
        ).count()
        active_users["last_30_days"] = User.objects.filter(
            last_login__gte=now - timedelta(days=30)
        ).count()
    except Exception:
        pass

    return {
        "database": db_health,
        "storage": storage,
        "api": api_health,
        "errors": error_rates,
        "active_users": active_users,
        "timestamp": timezone.now().isoformat(),
    }
