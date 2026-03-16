"""Services for admin management operations."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.announcements.models import Announcement
from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
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
