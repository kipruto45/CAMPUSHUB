"""
Permissions for resources app.
"""

from rest_framework import permissions


class IsResourceOwnerOrReadOnly(permissions.BasePermission):
    """Permission check for resource owner or read-only."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return (
                request.method in permissions.SAFE_METHODS and obj.status == "approved"
            )

        if request.user.is_admin or request.user.is_moderator:
            return True

        if request.method in permissions.SAFE_METHODS:
            # Allow read access to approved resources or owner/admin/moderator
            if obj.status == "approved":
                return True
            return obj.uploaded_by == request.user

        # Owners can only modify resources while awaiting moderation.
        return obj.uploaded_by == request.user and obj.status == "pending"


class CanUploadResource(permissions.BasePermission):
    """Permission check for uploading resources."""

    def has_permission(self, request, view):
        return request.user.is_authenticated


class CanApproveResource(permissions.BasePermission):
    """Permission check for approving resources."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_moderator
        )


class CanViewPendingResource(permissions.BasePermission):
    """Permission check for viewing pending resources."""

    def has_object_permission(self, request, view, obj):
        if obj.status == "approved":
            return True
        return request.user.is_authenticated and (
            obj.uploaded_by == request.user
            or request.user.is_admin
            or request.user.is_moderator
        )


class CanShareResource(permissions.BasePermission):
    """Permission check for sharing only public approved resources."""

    message = "This resource cannot be shared."

    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if obj.status != "approved":
            self.message = "Only approved resources can be shared."
            return False
        if not obj.is_public:
            self.message = "Private resources cannot be shared."
            return False
        if bool(getattr(obj, "is_deleted", False)) or getattr(obj, "deleted_at", None):
            self.message = "Deleted resources cannot be shared."
            return False
        if bool(getattr(obj, "is_hidden", False)):
            self.message = "Hidden resources cannot be shared."
            return False
        return True
