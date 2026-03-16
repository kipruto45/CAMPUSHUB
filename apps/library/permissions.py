from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners to modify their resources.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class CanAccessLibrary(permissions.BasePermission):
    """
    Permission to check if user can access library features.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class CanManageStorage(permissions.BasePermission):
    """
    Permission to check if user can manage storage.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
