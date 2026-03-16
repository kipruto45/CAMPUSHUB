"""
Unified Permissions System for CampusHub.

Provides granular permission checking with service layer integration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Type

from django.http import HttpRequest


# Permission types
class PermissionType:
    """Permission type constants."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MODERATE = "moderate"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SHARE = "share"


@dataclass
class Permission:
    """Permission definition."""
    name: str
    type: str
    description: str
    check_function: Callable[[Any, Any], bool] = None


@dataclass
class PermissionResult:
    """Result of permission check."""
    granted: bool
    reason: str | None = None
    error_code: str | None = None
    
    @classmethod
    def allow(cls, reason: str = None) -> 'PermissionResult':
        return cls(granted=True, reason=reason)
    
    @classmethod
    def deny(cls, reason: str = None, error_code: str = None) -> 'PermissionResult':
        return cls(granted=False, reason=reason, error_code=error_code)


class PermissionChecker(ABC):
    """
    Base permission checker.
    
    Usage:
        class ResourcePermissionChecker(PermissionChecker):
            def check(self, user, obj, permission) -> PermissionResult:
                if not user.is_authenticated:
                    return PermissionResult.deny("Authentication required", "unauthenticated")
                # Custom logic...
                return PermissionResult.allow()
    """
    
    @abstractmethod
    def check(self, user, obj, permission: str) -> PermissionResult:
        """Check if user has permission."""
        pass
    
    def has_permission(self, user, obj, permission: str) -> bool:
        """Quick permission check."""
        return self.check(user, obj, permission).granted


class BasePermission(ABC):
    """
    Base class for DRF permissions.
    
    Usage:
        class IsOwner(BasePermission):
            def has_object_permission(self, request, view, obj):
                return obj.user == request.user
    """
    
    def has_permission(self, request: HttpRequest, view, obj=None) -> bool:
        """Check if request has permission."""
        return True
    
    def has_object_permission(self, request: HttpRequest, view, obj) -> bool:
        """Check if request has object permission."""
        return True


# Permission collections
class PermissionGroup:
    """Group multiple permissions."""
    
    def __init__(self, *permissions: Callable):
        self.permissions = permissions
    
    def __call__(self, user, obj=None) -> bool:
        return all(perm(user, obj) for perm in self.permissions)


class AnyPermission:
    """Pass if any permission passes."""
    
    def __init__(self, *permissions: Callable):
        self.permissions = permissions
    
    def __call__(self, user, obj=None) -> bool:
        return any(perm(user, obj) for perm in self.permissions)


# Predefined permission functions
def is_authenticated(user, obj=None) -> bool:
    """Check if user is authenticated."""
    return user is not None and getattr(user, 'is_authenticated', False)


def is_admin(user, obj=None) -> bool:
    """Check if user is admin."""
    return is_authenticated(user) and getattr(user, 'is_admin', False)


def is_moderator(user, obj=None) -> bool:
    """Check if user is moderator."""
    return is_authenticated(user) and getattr(user, 'is_moderator', False)


def is_owner(user, obj, field: str = 'user') -> bool:
    """Check if user is owner of object."""
    if not is_authenticated(user):
        return False

    candidate_fields = [field]
    if field == 'user':
        candidate_fields.extend(['owner', 'uploaded_by', 'author', 'created_by'])

    for candidate in candidate_fields:
        obj_user = getattr(obj, candidate, None)
        if obj_user is None:
            continue
        return getattr(obj_user, 'id', obj_user) == user.id

    return False


def is_owner_or_admin(user, obj, field: str = 'user') -> bool:
    """Check if user is owner or admin."""
    return is_owner(user, obj, field) or is_admin(user)


def is_owner_or_moderator(user, obj, field: str = 'user') -> bool:
    """Check if user is owner or moderator."""
    return is_owner(user, obj, field) or is_moderator(user)


def is_verified(user, obj=None) -> bool:
    """Check if user is verified."""
    return is_authenticated(user) and getattr(user, 'is_verified', False)


def is_active(user, obj=None) -> bool:
    """Check if user is active."""
    return is_authenticated(user) and getattr(user, 'is_active', False)


def is_public(user, obj=None) -> bool:
    """Public access always allowed."""
    return True


def is_same_user(user, obj) -> bool:
    """Check if user is the same as obj (for user-specific operations)."""
    if not is_authenticated(user):
        return False
    return user.id == obj.id


def can_upload_resource(user, obj=None) -> bool:
    """Check if user can upload resources."""
    if not is_authenticated(user):
        return False
    role = getattr(user, 'role', None)
    return role and str(role).upper() in ["STUDENT", "ADMIN", "MODERATOR"]


def can_approve_resource(user, obj=None) -> bool:
    """Check if user can approve resources."""
    return is_admin(user) or is_moderator(user)


def can_moderate_content(user, obj=None) -> bool:
    """Check if user can moderate content."""
    return is_admin(user) or is_moderator(user)


# Resource-specific permissions
class ResourcePermissionChecker(PermissionChecker):
    """Permission checker for resources."""
    
    def check(self, user, obj, permission: str) -> PermissionResult:
        if not is_authenticated(user):
            return PermissionResult.deny("Authentication required", "unauthenticated")
        
        # Read permissions
        if permission == PermissionType.READ:
            if obj.is_public or obj.status == 'approved':
                return PermissionResult.allow()
            # Owner, admin, moderator can see non-public
            if is_owner_or_admin(user, obj, 'uploaded_by'):
                return PermissionResult.allow()
            if is_moderator(user):
                return PermissionResult.allow()
            return PermissionResult.deny("Access denied", "forbidden")
        
        # Write permissions
        if permission == PermissionType.WRITE:
            if is_owner_or_admin(user, obj, 'uploaded_by'):
                return PermissionResult.allow()
            return PermissionResult.deny("Not authorized to edit", "forbidden")
        
        # Delete permissions
        if permission == PermissionType.DELETE:
            if is_owner_or_admin(user, obj, 'uploaded_by'):
                return PermissionResult.allow()
            if is_moderator(user):
                return PermissionResult.allow()
            return PermissionResult.deny("Not authorized to delete", "forbidden")
        
        # Admin permissions
        if permission == PermissionType.ADMIN:
            if is_admin(user):
                return PermissionResult.allow()
            return PermissionResult.deny("Admin access required", "admin_required")
        
        return PermissionResult.deny("Unknown permission", "invalid_permission")


# Personal resource permissions
class PersonalResourcePermissionChecker(PermissionChecker):
    """Permission checker for personal resources."""
    
    def check(self, user, obj, permission: str) -> PermissionResult:
        if not is_authenticated(user):
            return PermissionResult.deny("Authentication required", "unauthenticated")
        
        # Check ownership
        if not is_owner(user, obj):
            return PermissionResult.deny("Not your resource", "forbidden")
        
        return PermissionResult.allow()


# Comment permissions
class CommentPermissionChecker(PermissionChecker):
    """Permission checker for comments."""
    
    def check(self, user, obj, permission: str) -> PermissionResult:
        if not is_authenticated(user):
            return PermissionResult.deny("Authentication required", "unauthenticated")
        
        # Anyone can read
        if permission == PermissionType.READ:
            return PermissionResult.allow()
        
        # Write/Delete - owner only
        if permission in [PermissionType.WRITE, PermissionType.DELETE]:
            if is_owner(user, obj, 'author'):
                return PermissionResult.allow()
            if is_admin(user) or is_moderator(user):
                return PermissionResult.allow()
            return PermissionResult.deny("Not authorized", "forbidden")
        
        return PermissionResult.allow()


# DRF Permission classes
class IsAuthenticated(BasePermission):
    """Allow authenticated users."""
    
    def has_permission(self, request, view):
        return is_authenticated(request.user)


class IsAdmin(BasePermission):
    """Allow admin users."""
    
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsModerator(BasePermission):
    """Allow moderator users."""
    
    def has_permission(self, request, view):
        return is_moderator(request.user)


class IsAdminOrModerator(BasePermission):
    """Allow admin or moderator users."""
    
    def has_permission(self, request, view):
        return is_admin(request.user) or is_moderator(request.user)


class IsOwner(BasePermission):
    """Allow object owner."""
    
    def has_object_permission(self, request, view, obj):
        return is_owner(request.user, obj)


class IsOwnerOrReadOnly(BasePermission):
    """Allow owner or read-only."""
    
    def has_object_permission(self, request, view, obj):
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True
        return is_owner(request.user, obj)


class IsVerifiedUser(BasePermission):
    """Allow verified users."""
    
    def has_permission(self, request, view):
        return is_verified(request.user)


class IsActiveUser(BasePermission):
    """Allow active users."""
    
    def has_permission(self, request, view):
        return is_active(request.user)


class CanApproveResource(BasePermission):
    """Allow resource approval."""
    
    def has_permission(self, request, view):
        return can_approve_resource(request.user)


class CanModerateContent(BasePermission):
    """Allow content moderation."""
    
    def has_permission(self, request, view):
        return can_moderate_content(request.user)


class CanUploadResource(BasePermission):
    """Allow resource upload."""
    
    def has_permission(self, request, view):
        return can_upload_resource(request.user)


class IsPublicResource(BasePermission):
    """Allow public resources."""
    
    def has_permission(self, request, view):
        return True


class IsApprovedResource(BasePermission):
    """Allow approved resources."""
    
    def has_object_permission(self, request, view, obj):
        # Allow read for approved resources
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            status = getattr(obj, "status", "").lower()
            if status == "approved":
                return True
            # Allow owner/admin/moderator
            user = getattr(request, "user", None)
            if user and (is_owner(user, obj) or is_admin(user) or is_moderator(user)):
                return True
            return False
        return True


# Permission decorators
def permission_required(permission: str):
    """Decorator for view permission check."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            checker = ResourcePermissionChecker()
            result = checker.check(request.user, kwargs.get('obj'), permission)
            if not result.granted:
                from django.http import Http403
                raise Http403(result.reason)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Permission cache
class PermissionCache:
    """Cache permission checks."""
    
    _cache: dict = {}
    
    @classmethod
    def get(cls, key: str) -> bool | None:
        return cls._cache.get(key)
    
    @classmethod
    def set(cls, key: str, value: bool):
        cls._cache[key] = value
    
    @classmethod
    def clear(cls):
        cls._cache.clear()
    
    @classmethod
    def invalidate_user(cls, user_id: int):
        """Clear cache for user."""
        keys_to_remove = [k for k in cls._cache if k.startswith(f"user_{user_id}")]
        for key in keys_to_remove:
            del cls._cache[key]
