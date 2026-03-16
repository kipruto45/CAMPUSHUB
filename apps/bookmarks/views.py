"""
Views for bookmarks app.
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.resources.models import Resource

from .models import Bookmark
from .permissions import IsBookmarkOwner
from .serializers import (BookmarkCreateSerializer, BookmarkListSerializer,
                          BookmarkToggleSerializer)
from .services import BookmarkService


class BookmarkViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet for Bookmark model."""

    serializer_class = BookmarkListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bookmark.objects.none()
        params = self.request.query_params
        return BookmarkService.get_user_bookmarks(
            self.request.user,
            resource_type=params.get("resource_type"),
            course_id=params.get("course"),
            unit_id=params.get("unit"),
            sort=params.get("sort", "newest"),
        )

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), IsBookmarkOwner()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return BookmarkCreateSerializer
        return BookmarkListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bookmark = serializer.save()
        response_data = BookmarkListSerializer(
            bookmark, context={"request": request}
        ).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        bookmark = self.get_object()
        self.check_object_permissions(request, bookmark)
        BookmarkService.remove_bookmark(request.user, bookmark=bookmark)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent bookmarks."""
        limit = int(request.query_params.get("limit", 20))
        bookmarks = BookmarkService.get_recent_bookmarks(
            request.user, limit=max(1, min(limit, 50))
        )
        serializer = self.get_serializer(bookmarks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def count(self, request):
        """Get total bookmark count."""
        count = BookmarkService.get_user_bookmarks(request.user).count()
        return Response({"count": count})

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        """Toggle bookmark for a resource."""
        serializer = BookmarkToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource_id = serializer.validated_data["resource_id"]

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )
        result = BookmarkService.toggle_bookmark(request.user, resource)
        return Response(result)
