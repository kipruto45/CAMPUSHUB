"""
Permissions for comments app.
"""

from rest_framework import permissions


class IsCommentOwnerOrReadOnly(permissions.BasePermission):
    """Permission check for comment owner or read-only."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            obj.user == request.user
            or request.user.is_admin
            or request.user.is_moderator
        )
