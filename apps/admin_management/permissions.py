"""
Permissions for Admin Management Module.
"""

from rest_framework import permissions


def _admin_has_entitlement(user):
    if not user or not user.is_authenticated:
        return False, "Authentication required"

    if not user.is_admin:
        return False, "Admin access required"

    if getattr(user, "is_superuser", False):
        return True, None

    from apps.payments.freemium import ensure_default_trial, get_admin_access_status

    status = get_admin_access_status(user)
    if status.get("has_access"):
        return True, None

    if status.get("trial_eligible"):
        try:
            subscription = ensure_default_trial(user, source="admin_access")
        except Exception:
            subscription = None
        if subscription is not None:
            return True, None

    return False, status.get("reason") or "Admin subscription required"


class IsAdmin(permissions.BasePermission):
    """
    Permission to check if user is an admin.
    """

    def has_permission(self, request, view):
        allowed, message = _admin_has_entitlement(getattr(request, "user", None))
        if not allowed and message:
            self.message = message
        return allowed


class IsSuperAdmin(permissions.BasePermission):
    """
    Permission to check if user is a super admin.
    """

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read access to authenticated users,
    but write access only to admins.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return False
            if getattr(user, "is_moderator", False) and not getattr(user, "is_admin", False):
                return True
            allowed, message = _admin_has_entitlement(user)
            if not allowed and message:
                self.message = message
            return allowed

        allowed, message = _admin_has_entitlement(getattr(request, "user", None))
        if not allowed and message:
            self.message = message
        return allowed
