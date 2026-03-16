"""
Permissions for Admin Management Module.
"""

from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission to check if user is an admin.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_admin
        )


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
            return bool(
                request.user
                and request.user.is_authenticated
                and (request.user.is_admin or request.user.is_moderator)
            )
        return bool(
            request.user and request.user.is_authenticated and request.user.is_admin
        )
