"""
API views for study groups.
"""

from apps.social.models import StudyGroup, StudyGroupMember, StudyGroupPost, StudyGroupResource, StudyGroupPostLike, StudyGroupPostComment
from apps.resources.models import Resource
from apps.core.pagination import StandardResultsSetPagination
from apps.core.permissions.unified import IsOwner
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect

from .serializers import (
    StudyGroupCreateSerializer,
    StudyGroupListSerializer,
    StudyGroupMemberSerializer,
    StudyGroupPostCreateSerializer,
    StudyGroupPostSerializer,
    StudyGroupPostCommentSerializer,
    StudyGroupResourceSerializer,
    CreateStudyGroupResourceSerializer,
    StudyGroupUpdateSerializer,
    CreateInviteLinkSerializer,
    InviteLinkSerializer,
    InviteLinkValidateSerializer,
)
from .services import StudyGroupService
from .invite_services import StudyGroupInviteService


class StudyGroupListCreateView(generics.ListCreateAPIView):
    """List and create study groups."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyGroup.objects.none()
        return StudyGroupService.list_groups(self.request.user, self.request.query_params)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StudyGroupCreateSerializer
        return StudyGroupListSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = StudyGroupService.create_group(request.user, serializer.validated_data)
        output = StudyGroupListSerializer(group, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class StudyGroupDetailView(generics.RetrieveAPIView):
    """Retrieve study group details."""

    serializer_class = StudyGroupListSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "group_id"

    def get_object(self):
        return StudyGroupService.get_group(self.kwargs["group_id"], self.request.user)

    def get_serializer_context(self):
        return {"request": self.request}


class StudyGroupUpdateView(generics.UpdateAPIView):
    """Update study group - only accessible by group creator."""

    serializer_class = StudyGroupUpdateSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    lookup_url_kwarg = "group_id"

    def get_object(self):
        group = StudyGroupService.get_group(self.kwargs["group_id"])
        # Check if user is the creator
        if group.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the group creator can update this group.")
        return group

    def get_serializer_context(self):
        return {"request": self.request}


class StudyGroupDeleteView(generics.DestroyAPIView):
    """Delete study group - only accessible by group creator."""

    permission_classes = [IsAuthenticated, IsOwner]
    lookup_url_kwarg = "group_id"

    def get_object(self):
        group = StudyGroupService.get_group(self.kwargs["group_id"])
        # Check if user is the creator
        if group.creator_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the group creator can delete this group.")
        return group

    def perform_destroy(self, instance):
        # Soft delete by setting status to deleted
        instance.status = "deleted"
        instance.save()


class StudyGroupJoinView(APIView):
    """Join a study group."""

    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = StudyGroupService.get_group(group_id)
        membership, created = StudyGroupService.join_group(request.user, group)
        return Response(
            {
                "joined": True,
                "created": created,
                "member": StudyGroupMemberSerializer(
                    membership, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class StudyGroupLeaveView(APIView):
    """Leave a study group."""

    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = StudyGroupService.get_group(group_id, request.user)
        StudyGroupService.leave_group(request.user, group)
        return Response({"left": True}, status=status.HTTP_200_OK)


class StudyGroupMembersView(generics.ListAPIView):
    """List active members of a study group."""

    serializer_class = StudyGroupMemberSerializer
    permission_classes = [IsAuthenticated]
    queryset = StudyGroupMember.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyGroupMember.objects.none()
        group = StudyGroupService.get_group(self.kwargs["group_id"], self.request.user)
        return StudyGroupService.list_members(group)

    def get_serializer_context(self):
        return {"request": self.request}


class StudyGroupPostsView(generics.ListCreateAPIView):
    """List and create study group posts."""

    permission_classes = [IsAuthenticated]
    queryset = StudyGroupPost.objects.none()

    def get_group(self):
        return StudyGroupService.get_group(self.kwargs["group_id"], self.request.user)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyGroupPost.objects.none()
        return StudyGroupService.list_posts(self.get_group())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StudyGroupPostCreateSerializer
        return StudyGroupPostSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = StudyGroupService.create_post(
            request.user, self.get_group(), serializer.validated_data
        )
        output = StudyGroupPostSerializer(post, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class StudyGroupPostLikeView(APIView):
    """Like or unlike a study group post."""

    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, post_id):
        post = get_object_or_404(StudyGroupPost, id=post_id, group_id=group_id)
        
        # Check if user is a member of the group
        if not StudyGroupMember.objects.filter(
            group=post.group, user=request.user, status="active"
        ).exists():
            return Response(
                {"error": "You must be a member of this group to like posts"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        like, created = StudyGroupPostLike.objects.get_or_create(
            post=post, user=request.user
        )
        
        if not created:
            # Unlike - remove the like
            like.delete()
            post.likes_count = max(0, post.likes_count - 1)
            post.save(update_fields=["likes_count"])
            return Response({"liked": False, "likes_count": post.likes_count})
        
        post.likes_count += 1
        post.save(update_fields=["likes_count"])
        return Response({"liked": True, "likes_count": post.likes_count})


class StudyGroupPostCommentsView(generics.ListCreateAPIView):
    """List and create comments on a study group post."""

    permission_classes = [IsAuthenticated]
    serializer_class = StudyGroupPostCommentSerializer

    def get_post(self):
        return get_object_or_404(
            StudyGroupPost, 
            id=self.kwargs["post_id"], 
            group_id=self.kwargs["group_id"]
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyGroupPostComment.objects.none()
        return StudyGroupPostComment.objects.filter(
            post=self.get_post()
        ).select_related("author")

    def perform_create(self, serializer):
        post = self.get_post()
        # Check if user is a member of the group
        if not StudyGroupMember.objects.filter(
            group=post.group, user=self.request.user, status="active"
        ).exists():
            raise PermissionError("You must be a member of this group to comment")
        
        serializer.save(post=post, author=self.request.user)
        
        # Update comments count
        post.comments_count += 1
        post.save(update_fields=["comments_count"])


class StudyGroupResourcesView(APIView):
    """List and share resources in a study group."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request, group_id, *args, **kwargs):
        """List resources shared in a study group."""
        group = StudyGroupService.get_group(group_id, request.user)
        resources = StudyGroupService.list_resources(group)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(resources, request, view=self)
        serializer = StudyGroupResourceSerializer(
            page if page is not None else resources,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request, group_id, *args, **kwargs):
        """Share a resource in a study group."""
        group = StudyGroupService.get_group(group_id, request.user)
        
        # Check if user is a member
        membership = StudyGroupMember.objects.filter(
            group=group, user=request.user, status='active'
        ).first()
        
        if not membership:
            return Response(
                {"error": "You must be a member of this group to share resources"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CreateStudyGroupResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            resource = Resource.objects.get(id=serializer.validated_data["resource_id"])
        except Resource.DoesNotExist:
            return Response(
                {"error": "Resource not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if resource is already shared in this group
        if StudyGroupResource.objects.filter(group=group, resource=resource).exists():
            return Response(
                {"error": "This resource is already shared in this group"},
                status=status.HTTP_400_BAD_REQUEST
            )

        study_group_resource = StudyGroupResource.objects.create(
            group=group,
            resource=resource,
            shared_by=request.user,
            description=serializer.validated_data.get("description", "")
        )

        return Response(
            StudyGroupResourceSerializer(study_group_resource, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )


class MyStudyGroupsView(APIView):
    """
    Get user's study groups.

    GET /api/social/study-groups/my-groups/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get groups where user is a member
        memberships = StudyGroupMember.objects.filter(
            user=request.user,
            status='active'
        ).select_related('group', 'group__course')

        groups_data = []
        for membership in memberships:
            group = membership.group
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'member_count': group.member_count,
                'course_name': group.course.name if group.course else None,
            })

        return Response(groups_data)


class StudyGroupInviteLinksView(APIView):
    """
    Create and list invite links for a study group.
    
    POST /api/social/study-groups/{group_id}/invite-links/
    GET /api/social/study-groups/{group_id}/invite-links/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = StudyGroupService.get_group(group_id, request.user)
        
        # Check if user can generate invites
        if not StudyGroupInviteService.can_generate_invite(group, request.user):
            return Response(
                {"error": "You don't have permission to manage invite links for this group"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        links = StudyGroupInviteService.get_invite_links(group)
        serializer = InviteLinkSerializer(links, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, group_id):
        group = StudyGroupService.get_group(group_id, request.user)
        
        # Check if user can generate invites
        if not StudyGroupInviteService.can_generate_invite(group, request.user):
            return Response(
                {"error": "You don't have permission to create invite links for this group"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CreateInviteLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invite_link = StudyGroupInviteService.create_invite_link(
            group=group,
            created_by=request.user,
            expires_in_hours=serializer.validated_data.get("expires_in_hours"),
            allow_auto_join=serializer.validated_data.get("allow_auto_join", True),
            max_uses=serializer.validated_data.get("max_uses"),
            notes=serializer.validated_data.get("notes", ""),
        )
        
        output = InviteLinkSerializer(invite_link, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class StudyGroupInviteLinkRevokeView(APIView):
    """
    Revoke an invite link.
    
    POST /api/social/study-groups/invite-links/{token}/revoke/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        from .models import StudyGroupInviteLink
        
        try:
            invite_link = StudyGroupInviteLink.objects.get(token=token)
        except StudyGroupInviteLink.DoesNotExist:
            return Response(
                {"error": "Invite link not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user can revoke
        if not StudyGroupInviteService.can_revoke_invite(invite_link, request.user):
            return Response(
                {"error": "You don't have permission to revoke this invite link"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        StudyGroupInviteService.revoke_invite_link(invite_link, request.user)
        return Response({"success": True, "message": "Invite link revoked"})


class StudyGroupInviteLinkValidateView(APIView):
    """
    Validate an invite link.
    
    GET /api/social/study-groups/invite-links/{token}/validate/
    """

    permission_classes = []  # No auth required

    def get(self, request, token):
        validation = StudyGroupInviteService.validate_invite_token(
            token,
            user=request.user if request.user.is_authenticated else None
        )
        return Response(validation)


class StudyGroupInviteLandingView(APIView):
    """
    Public invite landing endpoint for shared links.

    GET /groups/invite/{token}/
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        validation = StudyGroupInviteService.validate_invite_token(
            token,
            user=request.user if request.user.is_authenticated else None
        )
        accept = request.headers.get("Accept", "")
        wants_html = "text/html" in accept or "*/*" in accept

        frontend_base = (
            str(getattr(settings, "FRONTEND_URL", "")).rstrip("/")
            or str(getattr(settings, "RESOURCE_SHARE_BASE_URL", "")).rstrip("/")
            or str(getattr(settings, "WEB_APP_URL", "")).rstrip("/")
        )
        deeplink_scheme = str(
            getattr(settings, "MOBILE_DEEPLINK_SCHEME", "campushub")
        ).strip() or "campushub"

        if wants_html:
            if validation.get("valid"):
                if frontend_base:
                    target = f"{frontend_base}/group-invite?token={token}"
                else:
                    target = f"{deeplink_scheme}://group-invite?token={token}"
                return HttpResponseRedirect(target)

            html = """
            <html><head><title>Invite not available</title></head>
            <body style='font-family: system-ui, -apple-system, sans-serif; padding: 32px; text-align: center;'>
                <h2>Invite not available</h2>
                <p>This group invite link is invalid, expired, or revoked.</p>
                <p>Ask the group owner to send you a fresh invite.</p>
            </body></html>
            """
            return HttpResponse(html, status=status.HTTP_404_NOT_FOUND)

        status_code = status.HTTP_200_OK if validation.get("valid") else status.HTTP_404_NOT_FOUND
        return Response(validation, status=status_code)


class StudyGroupInviteLinkJoinView(APIView):
    """
    Join a study group via invite link.
    
    POST /api/social/study-groups/invite-links/{token}/join/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        result = StudyGroupInviteService.join_via_invite(token, request.user)
        
        if result["success"]:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
