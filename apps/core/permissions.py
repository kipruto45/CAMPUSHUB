"""
Custom permissions for CampusHub.
"""

from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission check for admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsModerator(permissions.BasePermission):
    """
    Permission check for moderator users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_moderator


class IsAdminOrModerator(permissions.BasePermission):
    """
    Permission check for admin or moderator users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_moderator
        )


class IsOwner(permissions.BasePermission):
    """
    Permission check for object owner.
    """

    def has_object_permission(self, request, view, obj):
        # Check if user is the owner of the object
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "uploaded_by"):
            return obj.uploaded_by == request.user
        if hasattr(obj, "author"):
            return obj.author == request.user
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission check for object owner or read-only.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is the owner
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "uploaded_by"):
            return obj.uploaded_by == request.user
        if hasattr(obj, "author"):
            return obj.author == request.user

        return False


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission check for verified users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_verified


class IsActiveUser(permissions.BasePermission):
    """
    Permission check for active users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active


class CanApproveResource(permissions.BasePermission):
    """
    Permission check for users who can approve resources.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_moderator
        )


class CanModerateContent(permissions.BasePermission):
    """
    Permission check for users who can moderate content.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_moderator
        )


class CanUploadResource(permissions.BasePermission):
    """
    Permission check for users who can upload resources.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            str(request.user.role).upper() in ["STUDENT", "ADMIN", "MODERATOR"]
        )


class IsPublicResource(permissions.BasePermission):
    """
    Permission check for public resources.
    """

    def has_permission(self, request, view):
        # Allow any request for public resources
        return True


class IsApprovedResource(permissions.BasePermission):
    """
    Permission check for approved resources.
    """

    def has_object_permission(self, request, view, obj):
        # Allow access to approved resources or owner/admin/moderator
        if request.method in permissions.SAFE_METHODS:
            if str(getattr(obj, "status", "")).lower() == "approved":
                return True
            # Allow owner or admin to view their own pending/rejected resources
            if hasattr(obj, "uploaded_by"):
                user = getattr(request, "user", None)
                return (
                    obj.uploaded_by == user
                    or bool(getattr(user, "is_admin", False))
                    or bool(getattr(user, "is_moderator", False))
                )
            return False
        return True
