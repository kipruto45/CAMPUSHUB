"""
Services for Study Group Invite Links.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import StudyGroup, StudyGroupInviteLink, StudyGroupMember

if TYPE_CHECKING:
    from apps.accounts.models import User

User = get_user_model()


class StudyGroupInviteService:
    """Service for managing study group invite links."""

    TOKEN_LENGTH = 16
    DEFAULT_INVITE_BASE_URL = "https://campushub.app"

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(StudyGroupInviteService.TOKEN_LENGTH)

    @classmethod
    def build_invite_url(cls, token: str, request=None) -> str:
        """Build the full invite URL."""
        if request is not None:
            try:
                return f"{request.build_absolute_uri('/').rstrip('/')}/groups/invite/{token}"
            except Exception:
                pass

        configured = (
            getattr(settings, "FRONTEND_URL", "")
            or getattr(settings, "RESOURCE_SHARE_BASE_URL", "")
            or getattr(settings, "WEB_APP_URL", "")
            or cls.DEFAULT_INVITE_BASE_URL
        )
        return f"{str(configured).strip().rstrip('/')}/groups/invite/{token}"

    @classmethod
    @transaction.atomic
    def create_invite_link(
        cls,
        group: StudyGroup,
        created_by: User,
        expires_in_hours: Optional[int] = None,
        allow_auto_join: bool = True,
        max_uses: Optional[int] = None,
        notes: str = "",
    ) -> StudyGroupInviteLink:
        """
        Create a new invite link for a study group.

        Args:
            group: The study group to create invite link for
            created_by: User creating the invite link
            expires_in_hours: Hours until link expires (None = never)
            allow_auto_join: Whether users can join directly
            max_uses: Maximum number of uses (None = unlimited)
            notes: Optional notes for the invite

        Returns:
            StudyGroupInviteLink: The created invite link
        """
        expires_at = None
        if expires_in_hours:
            expires_at = timezone.now() + timedelta(hours=expires_in_hours)

        invite_link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=created_by,
            token=cls.generate_token(),
            is_active=True,
            expires_at=expires_at,
            max_uses=max_uses,
            allow_auto_join=allow_auto_join,
            notes=notes,
        )

        return invite_link

    @classmethod
    def get_invite_links(cls, group: StudyGroup) -> list:
        """Get all invite links for a group."""
        return list(
            group.invite_links.all()
        )

    @classmethod
    @transaction.atomic
    def revoke_invite_link(cls, invite_link: StudyGroupInviteLink, revoked_by: User) -> bool:
        """
        Revoke an invite link.

        Args:
            invite_link: The invite link to revoke
            revoked_by: User revoking the link

        Returns:
            bool: True if successful
        """
        invite_link.is_active = False
        invite_link.save(update_fields=["is_active"])
        return True

    @classmethod
    def validate_invite_token(cls, token: str, user: Optional[User] = None) -> dict:
        """
        Validate an invite token and return information about it.

        Args:
            token: The invite token to validate
            user: The user trying to use the invite (optional)

        Returns:
            dict: Validation result with keys:
                - valid: bool
                - group: dict or None
                - already_member: bool
                - can_join_directly: bool
                - message: str
        """
        try:
            invite_link = StudyGroupInviteLink.objects.select_related(
                "group", "group__course"
            ).get(token=token)
        except StudyGroupInviteLink.DoesNotExist:
            return {
                "valid": False,
                "group": None,
                "already_member": False,
                "can_join_directly": False,
                "message": "Invalid invite link",
            }

        # Check if link is active
        if not invite_link.is_active:
            return {
                "valid": False,
                "group": cls._serialize_group(invite_link.group),
                "already_member": False,
                "can_join_directly": False,
                "message": "This invite link has been revoked",
            }

        # Check if link is expired
        if invite_link.is_expired:
            return {
                "valid": False,
                "group": cls._serialize_group(invite_link.group),
                "already_member": False,
                "can_join_directly": False,
                "message": "This invite link has expired",
            }

        # Check if max uses reached
        if invite_link.max_uses and invite_link.use_count >= invite_link.max_uses:
            return {
                "valid": False,
                "group": cls._serialize_group(invite_link.group),
                "already_member": False,
                "can_join_directly": False,
                "message": "This invite link has reached its maximum uses",
            }

        # Check if user is already a member
        already_member = False
        if user and user.is_authenticated:
            already_member = StudyGroupMember.objects.filter(
                group=invite_link.group,
                user=user,
                status="active"
            ).exists()

        if already_member:
            return {
                "valid": True,
                "group": cls._serialize_group(invite_link.group),
                "already_member": True,
                "can_join_directly": False,
                "message": "You are already a member of this group",
            }

        # Determine if user can join directly
        can_join_directly = invite_link.allow_auto_join

        return {
            "valid": True,
            "group": cls._serialize_group(invite_link.group),
            "already_member": False,
            "can_join_directly": can_join_directly,
            "message": "Valid invite link" if can_join_directly else "Join request required",
        }

    @classmethod
    @transaction.atomic
    def join_via_invite(cls, token: str, user: User) -> dict:
        """
        Join a study group via an invite link.

        Args:
            token: The invite token
            user: The user joining

        Returns:
            dict: Result with keys:
                - success: bool
                - message: str
                - group: dict or None
        """
        if not user.is_authenticated:
            return {
                "success": False,
                "message": "Please log in to join this group",
                "group": None,
            }

        # Validate the token
        validation = cls.validate_invite_token(token, user)
        
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"],
                "group": validation["group"],
            }

        if validation["already_member"]:
            return {
                "success": True,
                "message": "You are already a member of this group",
                "group": validation["group"],
            }

        invite_link = StudyGroupInviteLink.objects.select_related("group").get(token=token)
        group = invite_link.group

        # Check if group is at max capacity
        active_members = StudyGroupMember.objects.filter(
            group=group,
            status="active"
        ).count()

        if group.max_members and active_members >= group.max_members:
            return {
                "success": False,
                "message": "This group is full",
                "group": cls._serialize_group(group),
            }

        # Determine membership status based on group privacy and invite settings
        if validation["can_join_directly"]:
            # Create active membership
            StudyGroupMember.objects.get_or_create(
                user=user,
                group=group,
                defaults={"role": "member", "status": "active"}
            )
            
            # Increment use count
            invite_link.use_count += 1
            invite_link.last_used_at = timezone.now()
            invite_link.save(update_fields=["use_count", "last_used_at"])

            # Notify group admins
            cls._notify_group_join(group, user, joined=True)

            return {
                "success": True,
                "message": "You joined the study group successfully",
                "group": cls._serialize_group(group),
            }
        else:
            # Create pending membership request
            membership, created = StudyGroupMember.objects.get_or_create(
                user=user,
                group=group,
                defaults={"role": "member", "status": "pending"}
            )

            if not created and membership.status == "pending":
                return {
                    "success": True,
                    "message": "Your request to join has already been sent",
                    "group": cls._serialize_group(group),
                }

            # Notify group admins
            cls._notify_group_join(group, user, joined=False)

            return {
                "success": True,
                "message": "Your request to join has been sent",
                "group": cls._serialize_group(group),
            }

    @staticmethod
    def can_generate_invite(group: StudyGroup, user: User) -> bool:
        """
        Check if a user can generate invite links for a group.

        Args:
            group: The study group
            user: The user to check

        Returns:
            bool: True if user can generate invites
        """
        if not user.is_authenticated:
            return False

        # Owner can always generate invites
        if group.creator_id == user.id:
            return True

        # Check if user is an admin or moderator
        try:
            membership = StudyGroupMember.objects.get(group=group, user=user, status="active")
            return membership.role in ["admin", "moderator"]
        except StudyGroupMember.DoesNotExist:
            return False

    @staticmethod
    def can_revoke_invite(invite_link: StudyGroupInviteLink, user: User) -> bool:
        """
        Check if a user can revoke an invite link.

        Args:
            invite_link: The invite link
            user: The user to check

        Returns:
            bool: True if user can revoke
        """
        if not user.is_authenticated:
            return False

        # Creator of the invite or group owner can revoke
        if invite_link.created_by_id == user.id:
            return True

        if invite_link.group.creator_id == user.id:
            return True

        # Check if user is admin/moderator
        try:
            membership = StudyGroupMember.objects.get(
                group=invite_link.group,
                user=user,
                status="active"
            )
            return membership.role in ["admin", "moderator"]
        except StudyGroupMember.DoesNotExist:
            return False

    @staticmethod
    def _serialize_group(group: StudyGroup) -> dict:
        """Serialize group information for API response."""
        return {
            "id": str(group.id),
            "name": group.name,
            "description": group.description,
            "course": group.course.name if group.course else None,
            "unit": group.course.name if group.course else None,  # Using course as unit
            "privacy": group.privacy,
            "member_count": group.member_count,
            "max_members": group.max_members,
            "is_public": group.is_public,
        }

    @staticmethod
    def _notify_group_join(group: StudyGroup, user: User, joined: bool):
        """
        Notify group admins about a new member or join request.

        Args:
            group: The study group
            user: The user who joined/requested
            joined: True if directly joined, False if request pending
        """
        from apps.notifications.models import Notification

        # Get group admins and owner
        admin_ids = [group.creator_id]
        admin_ids.extend(
            StudyGroupMember.objects.filter(
                group=group,
                status="active",
                role__in=["admin", "moderator"]
            ).values_list("user_id", flat=True)
        )

        admin_ids = set(admin_ids)
        admin_ids.discard(user.id)  # Don't notify the user themselves

        title = "New Member" if joined else "Join Request"
        message = f"{user.full_name or user.username} "
        message += f"joined" if joined else f"requested to join"
        message += f" {group.name}"

        if not joined:
            message += ". Please review their request."

        for admin_id in admin_ids:
            try:
                Notification.objects.create(
                    recipient_id=admin_id,
                    title=title,
                    message=message,
                    notification_type="system",
                    link=f"/groups/{group.id}/",
                )
            except Exception:
                pass  # Don't fail if notification fails
