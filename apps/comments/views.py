"""
Views for comments app.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrModerator
from apps.moderation.services import ModerationService

from .models import Comment
from .permissions import IsCommentOwnerOrReadOnly
from .serializers import (CommentCreateSerializer, CommentSerializer,
                          ReplySerializer)


class CommentViewSet(viewsets.ModelViewSet):
    """ViewSet for Comment model."""

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsCommentOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["resource"]

    def get_serializer_class(self):
        if self.action == "create":
            return CommentCreateSerializer
        return CommentSerializer

    def get_permissions(self):
        if self.action in ["lock", "unlock"]:
            return [IsAuthenticated(), IsAdminOrModerator()]
        return [permission() for permission in self.permission_classes]

    @staticmethod
    def _as_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_queryset(self):
        queryset = Comment.objects.all()
        if self.action == "list":
            # Keep list endpoint focused on top-level threads.
            return queryset.filter(parent__isnull=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_locked and not (
            request.user.is_admin or request.user.is_moderator
        ):
            raise PermissionDenied("This comment is locked by moderation.")
        # Soft delete
        instance.is_deleted = True
        instance.content = "[deleted]"
        instance.moderation_hidden = False
        instance.moderation_hidden_content = ""
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_locked and not (
            request.user.is_admin or request.user.is_moderator
        ):
            raise PermissionDenied("This comment is locked by moderation.")
        instance.is_edited = True
        instance.save(update_fields=["is_edited"])
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def replies(self, request, pk=None):
        """Get replies to a comment."""
        comment = self.get_object()
        replies = comment.replies.all()
        serializer = ReplySerializer(replies, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        """Lock comment for moderation."""
        comment = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        hide_content = self._as_bool(request.data.get("hide_content"), default=True)
        ModerationService.lock_comment(
            comment=comment,
            reviewer=request.user,
            reason=reason,
            hide_content=hide_content,
        )
        serializer = CommentSerializer(comment, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        """Unlock comment after moderation."""
        comment = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        restore_content = self._as_bool(
            request.data.get("restore_content"), default=True
        )
        ModerationService.unlock_comment(
            comment=comment,
            reviewer=request.user,
            reason=reason,
            restore_content=restore_content,
        )
        serializer = CommentSerializer(comment, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResourceCommentListView(generics.ListCreateAPIView):
    """List and create comments for a resource."""

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["resource_id"] = self.kwargs.get("resource_id")
        return context

    def get_queryset(self):
        resource_id = self.kwargs.get("resource_id")
        return Comment.objects.filter(resource_id=resource_id, parent__isnull=True)

    def perform_create(self, serializer):
        resource_id = self.kwargs.get("resource_id")
        serializer.save(user=self.request.user, resource_id=resource_id)
