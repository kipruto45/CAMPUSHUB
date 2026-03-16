"""Permissions for bookmarks app."""

from rest_framework import permissions


class IsBookmarkOwner(permissions.BasePermission):
    """Allow object access only to bookmark owner."""

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and obj.user_id == request.user.id
