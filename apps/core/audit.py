"""
Audit logging service for CampusHub.
Tracks all admin and important actions for security and compliance.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


class AuditAction:
    """Audit action types."""

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"

    # Resource actions
    RESOURCE_CREATED = "resource_created"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_DELETED = "resource_deleted"
    RESOURCE_APPROVED = "resource_approved"
    RESOURCE_REJECTED = "resource_rejected"
    RESOURCE_DOWNLOADED = "resource_downloaded"
    RESOURCE_VIEWED = "resource_viewed"

    # Academic actions
    FACULTY_CREATED = "faculty_created"
    FACULTY_UPDATED = "faculty_updated"
    FACULTY_DELETED = "faculty_deleted"
    DEPARTMENT_CREATED = "department_created"
    DEPARTMENT_UPDATED = "department_updated"
    DEPARTMENT_DELETED = "department_deleted"
    COURSE_CREATED = "course_created"
    COURSE_UPDATED = "course_updated"
    COURSE_DELETED = "course_deleted"
    UNIT_CREATED = "unit_created"
    UNIT_UPDATED = "unit_updated"
    UNIT_DELETED = "unit_deleted"

    # Report actions
    REPORT_CREATED = "report_created"
    REPORT_RESOLVED = "report_resolved"
    REPORT_DISMISSED = "report_dismissed"

    # Announcement actions
    ANNOUNCEMENT_CREATED = "announcement_created"
    ANNOUNCEMENT_UPDATED = "announcement_updated"
    ANNOUNCEMENT_DELETED = "announcement_deleted"
    ANNOUNCEMENT_PUBLISHED = "announcement_published"

    # System actions
    SETTINGS_UPDATED = "settings_updated"
    BACKUP_CREATED = "backup_created"
    CACHE_CLEARED = "cache_cleared"


class AuditLogger:
    """
    Service for logging audit events.
    """

    @staticmethod
    def log(
        action: str,
        user,
        description: str = None,
        target_type: str = None,
        target_id: int = None,
        changes: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Optional[object]:
        """
        Log an audit event.

        Args:
            action: Action type (use AuditAction constants)
            user: User performing the action
            description: Human-readable description
            target_type: Type of target (e.g., 'User', 'Resource')
            target_id: ID of the target object
            changes: Dictionary of field changes {field: {old: x, new: y}}
            ip_address: Client IP address
            user_agent: Client user agent
            metadata: Additional metadata

        Returns:
            Created AuditLog instance or None
        """
        try:
            from apps.core.models import AuditLog

            audit_log = AuditLog.objects.create(
                action=action,
                user=user,
                description=description,
                target_type=target_type,
                target_id=target_id,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata or {},
            )

            logger.info(f"Audit log created: {action} by {user}")
            return audit_log

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            return None

    @staticmethod
    def log_user_action(
        action: str,
        target_user,
        performing_user,
        description: str = None,
        ip_address: str = None,
        **kwargs,
    ) -> Optional:
        """
        Log a user-related action.

        Args:
            action: Action type
            target_user: User being acted upon
            performing_user: User performing the action
            description: Description of the action
            ip_address: Client IP
            **kwargs: Additional fields

        Returns:
            AuditLog instance
        """
        return AuditLogger.log(
            action=action,
            user=performing_user,
            description=description
            or f"{action.replace('_', ' ').title()}: {target_user.username}",
            target_type="User",
            target_id=target_user.id,
            ip_address=ip_address,
            **kwargs,
        )

    @staticmethod
    def log_resource_action(
        action: str,
        resource,
        user,
        description: str = None,
        changes: Dict = None,
        ip_address: str = None,
        **kwargs,
    ) -> Optional:
        """
        Log a resource-related action.

        Args:
            action: Action type
            resource: Resource being acted upon
            user: User performing the action
            description: Description
            changes: Field changes
            ip_address: Client IP
            **kwargs: Additional fields

        Returns:
            AuditLog instance
        """
        return AuditLogger.log(
            action=action,
            user=user,
            description=description
            or f"{action.replace('_', ' ').title()}: {resource.title}",
            target_type="Resource",
            target_id=resource.id,
            changes=changes,
            ip_address=ip_address,
            **kwargs,
        )

    @staticmethod
    def get_user_activity(user, days: int = 30, limit: int = 100) -> List:
        """
        Get recent activity for a user.

        Args:
            user: User instance
            days: Number of days to look back
            limit: Maximum number of records

        Returns:
            List of AuditLog instances
        """
        from apps.core.models import AuditLog

        since = timezone.now() - timezone.timedelta(days=days)

        return list(
            AuditLog.objects.filter(user=user, created_at__gte=since).order_by(
                "-created_at"
            )[:limit]
        )

    @staticmethod
    def get_target_history(target_type: str, target_id: int, limit: int = 50) -> List:
        """
        Get history for a target object.

        Args:
            target_type: Type of target
            target_id: ID of target
            limit: Maximum records

        Returns:
            List of AuditLog instances
        """
        from apps.core.models import AuditLog

        return list(
            AuditLog.objects.filter(
                target_type=target_type, target_id=target_id
            ).order_by("-created_at")[:limit]
        )

    @staticmethod
    def search_logs(
        action: str = None,
        user_id: int = None,
        target_type: str = None,
        target_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100,
    ) -> List:
        """
        Search audit logs with filters.

        Args:
            action: Filter by action type
            user_id: Filter by user ID
            target_type: Filter by target type
            target_id: Filter by target ID
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum records

        Returns:
            List of AuditLog instances
        """
        from apps.core.models import AuditLog

        queryset = AuditLog.objects.all()

        if action:
            queryset = queryset.filter(action=action)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        return list(queryset.order_by("-created_at")[:limit])


class AuditReport:
    """
    Generate audit reports.
    """

    @staticmethod
    def get_user_activity_report(user, start_date, end_date) -> Dict:
        """
        Generate activity report for a user.

        Args:
            user: User instance
            start_date: Report start date
            end_date: Report end date

        Returns:
            Dictionary with report data
        """
        from apps.core.models import AuditLog

        logs = AuditLog.objects.filter(
            user=user, created_at__gte=start_date, created_at__lte=end_date
        ).order_by("created_at")

        # Group by action
        action_counts = {}
        daily_activity = {}

        for log in logs:
            # Count actions
            action_counts[log.action] = action_counts.get(log.action, 0) + 1

            # Daily activity
            date_key = log.created_at.date().isoformat()
            daily_activity[date_key] = daily_activity.get(date_key, 0) + 1

        return {
            "user": str(user),
            "user_id": user.id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_actions": logs.count(),
            "action_breakdown": action_counts,
            "daily_activity": daily_activity,
        }

    @staticmethod
    def get_admin_actions_report(start_date, end_date) -> Dict:
        """
        Generate report of admin actions.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Dictionary with report data
        """
        from apps.core.models import AuditLog

        # Get all admin users
        admin_users = User.objects.filter(
            models.Q(is_staff=True) | models.Q(is_superuser=True)
        )

        admin_actions = AuditLog.objects.filter(
            user__in=admin_users, created_at__gte=start_date, created_at__lte=end_date
        ).order_by("created_at")

        # Group by admin
        admin_activity = {}
        for action in admin_actions:
            username = str(action.user)
            if username not in admin_activity:
                admin_activity[username] = {
                    "total": 0,
                    "actions": {},
                }

            admin_activity[username]["total"] += 1
            action_type = action.action
            admin_activity[username]["actions"][action_type] = (
                admin_activity[username]["actions"].get(action_type, 0) + 1
            )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_admin_actions": admin_actions.count(),
            "admin_activity": admin_activity,
        }


# Middleware for automatic audit logging
class AuditMiddleware:
    """
    Middleware for automatic audit logging.
    """

    @staticmethod
    def log_request(request, user):
        """
        Log incoming request for audit.

        Args:
            request: HTTP request
            user: Authenticated user

        Returns:
            None
        """
        # Only log for authenticated admin users
        if not user or not user.is_authenticated:
            return

        # Get client info
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

        # Log admin page visits (optional)
        if request.path.startswith("/admin/") and not request.path.endswith(
            "/autocomplete/"
        ):
            AuditLogger.log(
                action=AuditAction.SETTINGS_UPDATED,
                user=user,
                description=f"Admin page visited: {request.path}",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"method": request.method, "path": request.path},
            )
