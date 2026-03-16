"""
Core Permissions for CampusHub.

This module provides:
- Unified permission system
- Permission checkers
- DRF permission classes
"""

from apps.core.permissions.unified import (
    # Permission types
    PermissionType,
    # Results
    Permission,
    PermissionResult,
    # Checkers
    PermissionChecker,
    ResourcePermissionChecker,
    PersonalResourcePermissionChecker,
    CommentPermissionChecker,
    # Permission functions
    is_active,
    is_admin,
    is_authenticated,
    is_moderator,
    is_owner,
    is_owner_or_admin,
    is_owner_or_moderator,
    is_public,
    is_same_user,
    is_verified,
    can_approve_resource,
    can_moderate_content,
    can_upload_resource,
    # DRF classes
    AnyPermission,
    CanApproveResource,
    CanModerateContent,
    CanUploadResource,
    IsActiveUser,
    IsAdmin,
    IsAdminOrModerator,
    IsApprovedResource,
    IsAuthenticated,
    IsModerator,
    IsOwner,
    IsOwnerOrReadOnly,
    IsPublicResource,
    IsVerifiedUser,
    # Decorators
    PermissionGroup,
    permission_required,
    PermissionCache,
)

__all__ = [
    # Types
    "PermissionType",
    # Results
    "Permission",
    "PermissionResult",
    # Checkers
    "PermissionChecker",
    "ResourcePermissionChecker",
    "PersonalResourcePermissionChecker",
    "CommentPermissionChecker",
    # Functions
    "is_active",
    "is_admin",
    "is_authenticated",
    "is_moderator",
    "is_owner",
    "is_owner_or_admin",
    "is_owner_or_moderator",
    "is_public",
    "is_same_user",
    "is_verified",
    "can_approve_resource",
    "can_moderate_content",
    "can_upload_resource",
    # DRF classes
    "AnyPermission",
    "CanApproveResource",
    "CanModerateContent",
    "CanUploadResource",
    "IsActiveUser",
    "IsAdmin",
    "IsAdminOrModerator",
    "IsApprovedResource",
    "IsAuthenticated",
    "IsModerator",
    "IsOwner",
    "IsOwnerOrReadOnly",
    "IsPublicResource",
    "IsVerifiedUser",
    # Decorators
    "PermissionGroup",
    "permission_required",
    "PermissionCache",
]
