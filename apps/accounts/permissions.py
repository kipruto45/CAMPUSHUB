"""
Custom permissions for accounts app.
"""

from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    """Permission check for student users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "STUDENT"


class IsAdminUser(permissions.BasePermission):
    """Permission check for admin users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsModeratorUser(permissions.BasePermission):
    """Permission check for moderator users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_moderator or request.user.is_admin
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission check for object owner or read-only."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user or bool(
            getattr(request.user, "is_admin", False)
        )


class CanManageUser(permissions.BasePermission):
    """Permission check for managing users."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_admin or request.user.is_moderator
