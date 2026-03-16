"""
Permissions for downloads app.
"""

from rest_framework import permissions


class CanDownloadResource(permissions.BasePermission):
    """Permission to check if user can download a resource."""

    def has_object_permission(self, request, view, obj):
        # Check if resource is approved
        return obj.status == "approved"


class CanDownloadPersonalFile(permissions.BasePermission):
    """Permission to check if user can download a personal file."""

    def has_object_permission(self, request, view, obj):
        # Only owner can download their personal files
        return obj.user == request.user


class CanViewDownloadHistory(permissions.BasePermission):
    """Permission to check if user can view download history."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Users can only view their own download history
        return obj.user == request.user
