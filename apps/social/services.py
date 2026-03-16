"""
Service layer for study groups.
"""

from django.db.models import Q
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import StudyGroup, StudyGroupMember, StudyGroupPost


class StudyGroupService:
    """Business logic for study group flows."""

    @classmethod
    def list_groups(cls, user, params):
        queryset = (
            StudyGroup.objects.filter(status="active")
            .select_related("creator", "course")
            .prefetch_related("memberships")
            .order_by("-created_at")
        )
        if user and user.is_authenticated:
            queryset = queryset.filter(
                Q(is_public=True)
                | Q(creator=user)
                | Q(memberships__user=user, memberships__status="active")
            )
        else:
            queryset = queryset.filter(is_public=True)

        course_id = params.get("course_id") or params.get("course")
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        year = params.get("year") or params.get("year_of_study")
        if year:
            queryset = queryset.filter(year_of_study=year)

        scope = str(params.get("scope") or "").strip().lower()
        if scope == "my":
            queryset = queryset.filter(
                Q(creator=user) | Q(memberships__user=user, memberships__status="active")
            )
        elif scope == "public":
            queryset = queryset.filter(is_public=True)

        search = str(params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        return queryset.distinct()

    @classmethod
    def get_group(cls, group_id, user=None):
        try:
            group = (
                StudyGroup.objects.select_related("creator", "course")
                .prefetch_related("memberships")
                .get(id=group_id, status="active")
            )
            if group.is_public:
                return group
            if user and user.is_authenticated:
                if group.creator_id == user.id:
                    return group
                if group.memberships.filter(user=user, status="active").exists():
                    return group
            raise PermissionDenied("You do not have access to this study group.")
        except StudyGroup.DoesNotExist as exc:
            raise NotFound("Study group not found.") from exc

    @classmethod
    @transaction.atomic
    def create_group(cls, user, validated_data):
        group = StudyGroup.objects.create(creator=user, **validated_data)
        StudyGroupMember.objects.create(
            group=group,
            user=user,
            role="admin",
            status="active",
        )
        return group

    @classmethod
    @transaction.atomic
    def join_group(cls, user, group):
        membership = group.memberships.filter(user=user).first()
        if membership and membership.status == "active":
            return membership, False

        active_members = group.memberships.filter(status="active").count()
        if active_members >= group.max_members:
            raise ValidationError({"group": "This study group is already full."})

        if membership:
            if membership.status == "banned":
                raise PermissionDenied("You are banned from this study group.")
            membership.status = "active"
            if membership.role not in {"admin", "moderator"}:
                membership.role = "member"
            membership.save(update_fields=["status", "role", "updated_at"])
            return membership, True

        membership = StudyGroupMember.objects.create(
            group=group,
            user=user,
            role="member",
            status="active",
        )
        return membership, True

    @classmethod
    @transaction.atomic
    def leave_group(cls, user, group):
        membership = group.memberships.filter(user=user, status="active").first()
        if not membership:
            raise ValidationError({"group": "You are not a member of this study group."})
        membership.delete()

    @classmethod
    def require_active_member(cls, user, group):
        if group.creator_id == user.id:
            return
        if not group.memberships.filter(user=user, status="active").exists():
            raise PermissionDenied("You must join this study group first.")

    @classmethod
    def list_members(cls, group):
        return group.memberships.filter(status="active").select_related("user").order_by("joined_at")

    @classmethod
    def list_posts(cls, group):
        return group.posts.select_related("author").order_by("-is_pinned", "-created_at")

    @classmethod
    @transaction.atomic
    def create_post(cls, user, group, validated_data):
        cls.require_active_member(user, group)
        title = (validated_data.get("title") or "").strip() or validated_data["content"][:80]
        return StudyGroupPost.objects.create(
            group=group,
            author=user,
            title=title,
            content=validated_data["content"],
        )

    @classmethod
    def list_resources(cls, group):
        return group.resources.select_related("resource", "resource__uploaded_by").order_by("-created_at")
