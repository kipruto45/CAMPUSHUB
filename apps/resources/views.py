"""
Views for resources app.
"""

from uuid import UUID

from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import BooleanField, Count, Exists, IntegerField, OuterRef, Subquery, Value
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import (AllowAny, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import JWTAuthentication
from apps.bookmarks.services import BookmarkService
from apps.library.services import move_file_to_trash
from apps.moderation.services import ModerationService

from .filters import ResourceFilter
from .models import (Folder, FolderItem, PersonalFolder, PersonalResource,
                     Resource, UserStorage)
from .permissions import (CanShareResource, CanUploadResource,
                          IsResourceOwnerOrReadOnly)
from .serializers import (BulkActionSerializer, CourseProgressSerializer,
                          FolderContentsSerializer, FolderItemSerializer,
                          FolderMoveSerializer, FolderSerializer,
                          FolderTreeSerializer, MyUploadListSerializer,
                          PersonalFolderDetailSerializer,
                          PersonalFolderSerializer,
                          PersonalResourceListSerializer,
                          PersonalResourceSerializer,
                          RelatedResourceSerializer, ResourceActionSerializer,
                          ResourceCreateSerializer, ResourceDetailSerializer,
                          ResourceListSerializer, ResourcePreviewSerializer,
                          ResourceSerializer,
                          ResourceShareLinkSerializer,
                          ResourceShareTrackSerializer,
                          ResourceUpdateSerializer, SaveToLibrarySerializer,
                          ShareResultSerializer, ShareToStudentSerializer,
                          ShareToStudyGroupSerializer, TrendingResourceSerializer,
                          UserStorageSerializer)
from .services import (ResourceDetailService, ResourceDownloadService,
                       ResourceRatingService, ResourceReportService,
                       ResourceShareService, ResourceUploadService,
                       CourseProgressService)


@extend_schema_view(
    retrieve=extend_schema(operation_id="api_resources_slug_retrieve"),
    update=extend_schema(operation_id="api_resources_slug_update"),
    partial_update=extend_schema(operation_id="api_resources_slug_partial_update"),
    destroy=extend_schema(operation_id="api_resources_slug_destroy"),
    rate=extend_schema(operation_id="api_resources_slug_rate_create"),
)
class ResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for Resource model."""

    queryset = Resource.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ResourceFilter
    ordering_fields = [
        "created_at",
        "-created_at",
        "download_count",
        "-download_count",
        "view_count",
        "-view_count",
        "average_rating",
        "-average_rating",
    ]

    def get_serializer_class(self):
        if self.action == "list":
            return ResourceListSerializer
        if self.action == "create":
            return ResourceCreateSerializer
        if self.action in ["update", "partial_update"]:
            return ResourceUpdateSerializer
        if self.action in ["retrieve", "detail"]:
            return ResourceDetailSerializer
        if self.action == "preview":
            return ResourcePreviewSerializer
        if self.action == "share_link":
            return ResourceShareLinkSerializer
        if self.action == "share":
            return ResourceShareTrackSerializer
        return ResourceSerializer

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, slug=None):
        """Get comprehensive resource preview/profile information.
        
        Returns rich preview data including:
        - Uploader information with profile details
        - Academic metadata (faculty, department, course, year)
        - Engagement statistics (views, downloads, ratings, comments)
        - User interactions (is_favorited, is_bookmarked, user_rating)
        - Related resources and recommendations
        """
        instance = self.get_object()
        serializer = ResourcePreviewSerializer(
            instance, context={"request": request}
        )
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return super().list(request, *args, **kwargs)

        cache_key = f"resources:list:{request.get_full_path()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            cache.set(cache_key, response.data, 60)
        return response

    def get_queryset(self):
        from apps.favorites.models import FavoriteType

        queryset = Resource.objects.all().select_related(
            "uploaded_by",
            "faculty",
            "department",
            "course",
            "unit",
        ).annotate(
            comments_count=Count("comments", distinct=True),
            ratings_count=Count("ratings", distinct=True),
            likes_count=Count(
                "favorites",
                filter=models.Q(favorites__favorite_type=FavoriteType.RESOURCE),
                distinct=True,
            ),
        )

        # Filter based on user role
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status="approved", is_public=True)
            queryset = queryset.annotate(
                is_bookmarked=Value(False, output_field=BooleanField()),
                is_favorited=Value(False, output_field=BooleanField()),
                user_rating=Value(None, output_field=IntegerField()),
            )
        elif not (self.request.user.is_admin or self.request.user.is_moderator):
            queryset = queryset.filter(
                models.Q(status="approved") | models.Q(uploaded_by=self.request.user)
            )

        if self.request.user.is_authenticated:
            from apps.bookmarks.models import Bookmark
            from apps.favorites.models import Favorite, FavoriteType
            from apps.ratings.models import Rating

            queryset = queryset.annotate(
                is_bookmarked=Exists(
                    Bookmark.objects.filter(
                        user=self.request.user, resource=OuterRef("pk")
                    )
                ),
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=self.request.user,
                        favorite_type=FavoriteType.RESOURCE,
                        resource=OuterRef("pk"),
                    )
                ),
                user_rating=Subquery(
                    Rating.objects.filter(
                        user=self.request.user, resource=OuterRef("pk")
                    )
                    .values("value")[:1]
                ),
            )

        return queryset

    def get_permissions(self):
        if self.action == "create":
            return [CanUploadResource()]
        if self.action == "download":
            return [AllowAny()]
        if self.action == "share_link":
            return [AllowAny(), CanShareResource()]
        if self.action == "share":
            return [IsAuthenticated(), CanShareResource()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsResourceOwnerOrReadOnly()]
        return super().get_permissions()

    def get_object(self):
        """
        Resolve resources by slug and also allow UUID id for actions
        that call detail routes like /api/resources/{id}/bookmark/.
        """
        if self.action == "download":
            queryset = self.filter_queryset(Resource.objects.all())
        else:
            queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_field)

        obj = queryset.filter(**{self.lookup_field: lookup_value}).first()
        if obj is None:
            try:
                UUID(str(lookup_value))
                obj = queryset.filter(id=lookup_value).first()
            except (ValueError, TypeError):
                obj = None
        if obj is None:
            raise Http404

        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        try:
            resource = serializer.save()
        except (DRFValidationError, DjangoValidationError) as exc:
            if hasattr(exc, "detail"):
                detail = exc.detail
            elif hasattr(exc, "message_dict"):
                detail = exc.message_dict
            else:
                detail = {
                    "detail": exc.messages if hasattr(exc, "messages") else str(exc)
                }
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        output = ResourceSerializer(resource, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        service = ResourceDetailService(instance, request.user, request)
        service.track_view()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def detail(self, request, slug=None):
        """Get detailed resource information with user-specific data."""
        instance = self.get_object()
        service = ResourceDetailService(instance, request.user, request)
        service.track_view()

        serializer = ResourceDetailSerializer(instance, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def download(self, request, slug=None):
        """Record a download and return the file URL."""
        instance = self.get_object()
        service = ResourceDownloadService(instance, request.user)

        can_download, error = service.can_download()
        if not can_download:
            return Response({"detail": error}, status=status.HTTP_403_FORBIDDEN)

        service.record_download(request)

        # Return file URL
        file_url = None
        if instance.file:
            file_url = request.build_absolute_uri(instance.file.url)

        return Response(
            {"download_count": instance.download_count + 1, "file_url": file_url}
        )

    @action(detail=True, methods=["post", "delete"])
    def bookmark(self, request, slug=None):
        """Bookmark or remove bookmark."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        instance = self.get_object()
        if request.method.lower() == "delete":
            try:
                BookmarkService.remove_bookmark(request.user, resource=instance)
            except DRFValidationError:
                return Response(
                    {"detail": "Bookmark not found."}, status=status.HTTP_404_NOT_FOUND
                )
            result = {"is_bookmarked": False, "message": "Bookmark removed."}
        else:
            result = BookmarkService.toggle_bookmark(request.user, instance)
        return Response(result)

    @action(detail=True, methods=["post"])
    def rate(self, request, slug=None):
        """Rate the resource."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = ResourceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = self.get_object()
        service = ResourceRatingService(instance, request.user)
        result = service.rate(serializer.validated_data["value"])

        if result["success"]:
            return Response(result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["delete"], url_path="rate")
    def remove_rating(self, request, slug=None):
        """Remove user's rating."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        instance = self.get_object()
        service = ResourceRatingService(instance, request.user)
        result = service.remove_rating()

        return Response(result)

    @action(detail=True, methods=["post"])
    def report(self, request, slug=None):
        """Report the resource."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = ResourceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = self.get_object()
        service = ResourceReportService(instance, request.user)
        result = service.report(
            reason=serializer.validated_data.get("reason", "other"),
            message=serializer.validated_data.get("message", ""),
        )

        if result["success"]:
            return Response(result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def related(self, request, slug=None):
        """Get related resources."""
        instance = self.get_object()
        service = ResourceDetailService(instance, request.user)
        related = service.get_related_resources(limit=10)

        serializer = RelatedResourceSerializer(
            related, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="share-link")
    def share_link(self, request, slug=None):
        """Get share payload for a resource."""
        instance = self.get_object()
        service = ResourceShareService(
            instance,
            request.user if request.user.is_authenticated else None,
            request=request,
        )
        payload = service.get_share_payload()
        if not payload.get("can_share", False):
            return Response(payload, status=status.HTTP_403_FORBIDDEN)
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="share")
    def share(self, request, slug=None):
        """Record a resource share action and increment share counters."""
        instance = self.get_object()
        serializer = ResourceShareTrackSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        service = ResourceShareService(instance, request.user)
        try:
            result = service.record_share(
                method=serializer.validated_data.get("share_method", "other"),
                request=request,
            )
        except (DRFValidationError, DjangoValidationError) as exc:
            detail = (
                exc.detail
                if hasattr(exc, "detail")
                else (
                    getattr(exc, "message_dict", None)
                    or getattr(exc, "messages", None)
                    or str(exc)
                )
            )
            if isinstance(detail, dict):
                return Response(detail, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        # Track share for activity and gamification
        from .signals import track_resource_share
        track_resource_share(instance, request.user)

        return Response(result)

    @action(detail=True, methods=["post"], url_path="share-to-student")
    def share_to_student(self, request, slug=None):
        """
        Share a resource to a specific student.
        """
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        instance = self.get_object()
        serializer = ShareToStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        student_id = serializer.validated_data.get("student_id")
        message = serializer.validated_data.get("message", "")

        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Student not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Don't allow sharing to self
        if student.id == request.user.id:
            return Response(
                {"detail": "Cannot share resource with yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if resource can be shared
        can_share, error = ResourceShareService.can_share(instance, request.user)
        if not can_share:
            return Response(
                {"detail": error},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Send notification to the student
        from apps.notifications.services import NotificationService
        NotificationService.notify_resource_shared_with_user(
            recipient=student,
            sender=request.user,
            resource=instance,
            message=message,
        )

        # Record the share event
        service = ResourceShareService(instance, request.user)
        service.record_share(method="send_to_student", request=request)

        # Track activity
        from .signals import track_resource_share
        track_resource_share(instance, request.user)

        return Response({
            "success": True,
            "message": f"Resource shared with {student.get_full_name() or student.username}",
            "resource_id": str(instance.id),
            "shared_with": [student.get_full_name() or student.username],
        })

    @action(detail=True, methods=["post"], url_path="share-to-group")
    def share_to_group(self, request, slug=None):
        """
        Share a resource to a study group.
        """
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        instance = self.get_object()
        serializer = ShareToStudyGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.social.models import StudyGroup

        group_id = serializer.validated_data.get("group_id")
        message = serializer.validated_data.get("message", "")

        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            return Response(
                {"detail": "Study group not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if user is a member of the group
        if not group.is_member(request.user):
            return Response(
                {"detail": "You are not a member of this study group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if resource can be shared
        can_share, error = ResourceShareService.can_share(instance, request.user)
        if not can_share:
            return Response(
                {"detail": error},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Add resource to group
        from apps.social.models import StudyGroupResource
        study_group_resource, created = StudyGroupResource.objects.get_or_create(
            group=group,
            resource=instance,
            defaults={"shared_by": request.user, "description": message}
        )

        if not created:
            # Resource was already shared with the group
            return Response({
                "success": True,
                "message": f"Resource was already shared with {group.name}",
                "resource_id": str(instance.id),
                "shared_with": [group.name],
            })

        # Notify all group members
        from apps.notifications.services import NotificationService
        members = group.members.all()
        NotificationService.notify_resource_shared_to_group(
            recipients=members,
            sender=request.user,
            resource=instance,
            group_name=group.name,
            message=message,
        )

        # Record the share event
        service = ResourceShareService(instance, request.user)
        service.record_share(method="share_to_group", request=request)

        # Track activity
        from .signals import track_resource_share
        track_resource_share(instance, request.user)

        return Response({
            "success": True,
            "message": f"Resource shared with study group '{group.name}'",
            "resource_id": str(instance.id),
            "shared_with": [group.name],
        })

    @action(detail=False, methods=["get"])
    def trending(self, request):
        """Get trending resources."""
        resources = Resource.objects.filter(status="approved").order_by(
            "-download_count", "-view_count", "-average_rating"
        )[:20]
        serializer = TrendingResourceSerializer(resources, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recommended(self, request):
        """Get recommended resources based on user's course."""
        user = request.user
        if not user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        resources = (
            Resource.objects.filter(status="approved", course=user.course)
            .exclude(uploaded_by=user)
            .order_by("-average_rating", "-download_count")[:20]
        )

        serializer = ResourceListSerializer(
            resources, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_uploads(self, request):
        """Get user's uploaded resources."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        resources = ResourceUploadService.get_user_uploads(request.user)
        page = self.paginate_queryset(resources)
        if page is not None:
            serializer = MyUploadListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = MyUploadListSerializer(
            resources, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_action(self, request):
        """Perform bulk actions on resources."""
        if not (request.user.is_admin or request.user.is_moderator):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resource_ids = serializer.validated_data["resource_ids"]
        action = serializer.validated_data["action"]

        resources = Resource.objects.filter(id__in=resource_ids)

        if action == "delete":
            resources.delete()
        elif action == "approve":
            for resource in resources:
                ModerationService.approve_resource(
                    resource=resource,
                    reviewer=request.user,
                    reason="Bulk approval",
                )
        elif action == "reject":
            for resource in resources:
                ModerationService.reject_resource(
                    resource=resource,
                    reviewer=request.user,
                    reason="Bulk rejection",
                )
        elif action == "pin":
            resources.update(is_pinned=True)
        elif action == "unpin":
            resources.update(is_pinned=False)

        return Response({"message": f'Bulk action "{action}" completed successfully.'})

    @action(detail=False, methods=["get"])
    def storage(self, request):
        """Get user's storage usage."""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        storage, created = UserStorage.objects.get_or_create(user=request.user)
        serializer = UserStorageSerializer(storage)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pinned(self, request):
        """Get pinned resources."""
        resources = Resource.objects.filter(is_pinned=True, status="approved").order_by(
            "-created_at"
        )

        page = self.paginate_queryset(resources)
        if page is not None:
            serializer = ResourceListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = ResourceListSerializer(
            resources, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ResourceListView(generics.ListAPIView):
    """List all approved resources."""

    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ResourceFilter
    ordering_fields = [
        "created_at",
        "-created_at",
        "download_count",
        "-download_count",
        "view_count",
        "-view_count",
        "average_rating",
        "-average_rating",
    ]

    def get_queryset(self):
        queryset = Resource.objects.filter(status="approved")

        # Apply filters
        faculty_id = self.request.query_params.get("faculty")
        department_id = self.request.query_params.get("department")
        course_id = self.request.query_params.get("course")
        unit_id = self.request.query_params.get("unit")
        resource_type = self.request.query_params.get("resource_type")

        if faculty_id:
            queryset = queryset.filter(faculty_id=faculty_id)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        return queryset


class ResourceCreateView(generics.CreateAPIView):
    """Standalone create view for resource upload workflow."""

    serializer_class = ResourceCreateSerializer
    permission_classes = [IsAuthenticated]


class MyUploadsView(generics.ListAPIView):
    """List uploads owned by the authenticated user."""

    serializer_class = MyUploadListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        return ResourceUploadService.get_user_uploads(self.request.user)


class ResourceUpdateView(generics.RetrieveUpdateDestroyAPIView):
    """Update/delete own resource by id (owner pending only, or admin/moderator)."""

    serializer_class = ResourceUpdateSerializer
    permission_classes = [IsAuthenticated, IsResourceOwnerOrReadOnly]
    queryset = Resource.objects.all()

    @extend_schema(operation_id="api_resources_by_id_retrieve")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(operation_id="api_resources_by_id_update")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(operation_id="api_resources_by_id_partial_update")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(operation_id="api_resources_by_id_destroy")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class FolderViewSet(viewsets.ModelViewSet):
    """ViewSet for Folder model."""

    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Folder.objects.none()
        return Folder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def contents(self, request, pk=None):
        """Get folder contents."""
        folder = self.get_object()
        items = FolderItem.objects.filter(folder=folder)
        serializer = FolderItemSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_resource(self, request, pk=None):
        """Add resource to folder."""
        folder = self.get_object()
        resource_id = request.data.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        item, created = FolderItem.objects.get_or_create(
            folder=folder, resource=resource
        )

        if created:
            return Response(
                {"message": "Resource added to folder."}, status=status.HTTP_201_CREATED
            )
        return Response(
            {"message": "Resource already in folder."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["delete"])
    def remove_resource(self, request, pk=None):
        """Remove resource from folder."""
        folder = self.get_object()
        resource_id = request.query_params.get("resource_id")

        deleted_count = FolderItem.objects.filter(
            folder=folder, resource_id=resource_id
        ).delete()[0]

        if deleted_count:
            return Response({"message": "Resource removed from folder."})
        return Response(
            {"detail": "Resource not found in folder."},
            status=status.HTTP_404_NOT_FOUND,
        )


class SaveToLibraryView(generics.CreateAPIView):
    """Save resource to user's library (folder)."""

    permission_classes = [IsAuthenticated]
    serializer_class = FolderItemSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Get or create default "My Library" folder
        library, created = Folder.objects.get_or_create(
            user=request.user, name="My Library", defaults={"color": "#10b981"}
        )

        item, item_created = FolderItem.objects.get_or_create(
            folder=library, resource=resource
        )

        if item_created:
            return Response(
                {"message": "Resource saved to library."},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"message": "Resource already in library."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PersonalFolderViewSet(viewsets.ModelViewSet):
    """ViewSet for PersonalFolder model - personal library folders."""

    permission_classes = [IsAuthenticated]
    serializer_class = PersonalFolderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalFolder.objects.none()
        return PersonalFolder.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PersonalFolderDetailSerializer
        return PersonalFolderSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        """Toggle folder as favorite."""
        folder = self.get_object()
        folder.is_favorite = not folder.is_favorite
        folder.save(update_fields=["is_favorite"])
        return Response(
            {
                "is_favorite": folder.is_favorite,
                "message": (
                    "Folder favorited." if folder.is_favorite else "Folder unfavorited."
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def favorites(self, request):
        """Get all favorite folders."""
        folders = self.get_queryset().filter(is_favorite=True)
        serializer = self.get_serializer(folders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get folder tree structure."""
        # Get root folders (no parent)
        root_folders = self.get_queryset().filter(parent__isnull=True)
        serializer = FolderTreeSerializer(root_folders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def contents(self, request, pk=None):
        """Get folder contents (subfolders and files)."""
        folder = self.get_object()
        serializer = FolderContentsSerializer(folder, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Move folder to a different parent."""
        folder = self.get_object()
        serializer = FolderMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent_id = serializer.validated_data.get("parent_id")

        # Get target parent
        target_parent = None
        if parent_id:
            try:
                target_parent = PersonalFolder.objects.get(
                    id=parent_id, user=request.user
                )
            except PersonalFolder.DoesNotExist:
                return Response(
                    {"detail": "Target folder not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Check for circular reference
        if target_parent:
            # Cannot move folder into itself
            if target_parent.id == folder.id:
                return Response(
                    {"detail": "Cannot move folder into itself."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cannot move folder into its own descendant
            if self._is_descendant(folder, target_parent):
                return Response(
                    {"detail": "Cannot move folder into its own descendant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check for duplicate name in target parent
        existing = (
            PersonalFolder.objects.filter(
                user=request.user, name=folder.name, parent=target_parent
            )
            .exclude(id=folder.id)
            .exists()
        )

        if existing:
            return Response(
                {
                    "detail": "A folder with this name already exists in the target location."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder.parent = target_parent
        folder.save(update_fields=["parent"])

        return Response(PersonalFolderSerializer(folder).data)

    def _is_descendant(self, folder, potential_descendant):
        """Check if potential_descendant is a descendant of folder."""
        current = potential_descendant
        while current:
            if current.parent == folder:
                return True
            current = current.parent
        return False


class PersonalResourceViewSet(viewsets.ModelViewSet):
    """ViewSet for PersonalResource model - personal library files."""

    permission_classes = [IsAuthenticated]
    serializer_class = PersonalResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalResource.objects.none()
        return PersonalResource.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return PersonalResourceListSerializer
        return PersonalResourceSerializer

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a personal file and track the activity."""
        instance = self.get_object()
        # Track activity
        from apps.activity.services import ActivityService

        ActivityService.log_personal_file_open(
            user=request.user, personal_file=instance, request=request
        )
        # Update last accessed
        instance.mark_accessed()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Soft delete personal files by moving them to trash."""
        instance = self.get_object()
        try:
            move_file_to_trash(request.user, instance)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "File moved to trash."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        """Toggle file as favorite."""
        resource = self.get_object()
        resource.is_favorite = not resource.is_favorite
        resource.save(update_fields=["is_favorite"])
        return Response(
            {
                "is_favorite": resource.is_favorite,
                "message": (
                    "File favorited." if resource.is_favorite else "File unfavorited."
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def favorites(self, request):
        """Get all favorite files."""
        resources = self.get_queryset().filter(is_favorite=True)
        serializer = self.get_serializer(resources, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recently accessed files."""
        resources = (
            self.get_queryset()
            .filter(last_accessed_at__isnull=False)
            .order_by("-last_accessed_at")[:20]
        )
        serializer = self.get_serializer(resources, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def storage(self, request):
        """Get storage usage summary."""
        from .models import UserStorage

        storage, _ = UserStorage.objects.get_or_create(user=request.user)
        serializer = UserStorageSerializer(storage)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Move file to a different folder."""
        resource = self.get_object()
        folder_id = request.data.get("folder_id")

        if folder_id:
            try:
                folder = PersonalFolder.objects.get(id=folder_id, user=request.user)
                resource.folder = folder
            except PersonalFolder.DoesNotExist:
                return Response(
                    {"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            resource.folder = None

        resource.save(update_fields=["folder"])
        return Response(
            PersonalResourceSerializer(
                resource, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate a file."""
        resource = self.get_object()
        new_resource = PersonalResource.objects.create(
            user=request.user,
            folder=resource.folder,
            title=f"{resource.title} (Copy)",
            file=resource.file,
            file_type=resource.file_type,
            file_size=resource.file_size,
            description=resource.description,
            tags=resource.tags,
            visibility="private",
            source_type="imported",
        )
        return Response(
            PersonalResourceSerializer(
                new_resource, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class SaveToPersonalLibraryView(generics.CreateAPIView):
    """Save a public resource to personal library."""

    permission_classes = [IsAuthenticated]
    serializer_class = SaveToLibrarySerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        folder_id = request.data.get("folder_id")
        custom_title = request.data.get("title")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Get folder if provided
        folder = None
        if folder_id:
            try:
                folder = PersonalFolder.objects.get(id=folder_id, user=request.user)
            except PersonalFolder.DoesNotExist:
                return Response(
                    {"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND
                )

        # Check if already saved
        existing = PersonalResource.objects.filter(
            user=request.user, linked_public_resource=resource
        ).first()

        if existing:
            return Response(
                {"detail": "Resource already in your library.", "id": str(existing.id)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create personal resource
        personal_resource = PersonalResource.objects.create(
            user=request.user,
            folder=folder,
            title=custom_title or resource.title,
            file=resource.file,
            file_type=resource.file_type,
            file_size=resource.file_size,
            description=resource.description,
            tags=resource.tags,
            visibility="private",
            source_type="saved",
            linked_public_resource=resource,
        )

        return Response(
            PersonalResourceSerializer(
                personal_resource, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class RelatedResourcesView(generics.ListAPIView):
    """View for getting related resources."""

    serializer_class = RelatedResourceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Resource.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()

        resource_id = self.kwargs.get("resource_id")
        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Resource.objects.none()

        service = ResourceDetailService(resource, self.request.user)
        return service.get_related_resources(limit=10)


class LibraryDashboardView(APIView):
    """View for personal library dashboard."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get personal library dashboard data."""
        user = request.user

        # Get folders
        root_folders = PersonalFolder.objects.filter(
            user=user, parent__isnull=True
        ).order_by("-is_favorite", "name")

        # Get recent files
        recent_files = PersonalResource.objects.filter(
            user=user, last_accessed_at__isnull=False
        ).order_by("-last_accessed_at")[:10]

        # Get favorite folders
        favorite_folders = PersonalFolder.objects.filter(user=user, is_favorite=True)[
            :5
        ]

        # Get favorite files
        favorite_files = PersonalResource.objects.filter(user=user, is_favorite=True)[
            :10
        ]

        # Get storage info
        storage, _ = UserStorage.objects.get_or_create(user=user)
        storage_used_mb = storage.used_storage / (1024 * 1024)
        storage_limit_mb = storage.storage_limit / (1024 * 1024)

        # Get total counts
        total_folders = PersonalFolder.objects.filter(user=user).count()
        total_files = PersonalResource.objects.filter(user=user).count()

        return Response(
            {
                "folders": PersonalFolderSerializer(root_folders, many=True).data,
                "recent_files": PersonalResourceListSerializer(
                    recent_files, many=True, context={"request": request}
                ).data,
                "favorite_folders": PersonalFolderSerializer(
                    favorite_folders, many=True
                ).data,
                "favorite_files": PersonalResourceListSerializer(
                    favorite_files, many=True, context={"request": request}
                ).data,
                "storage": {
                    "used_mb": round(storage_used_mb, 2),
                    "limit_mb": round(storage_limit_mb, 2),
                    "percent_used": round(
                        (
                            (storage_used_mb / storage_limit_mb * 100)
                            if storage_limit_mb > 0
                            else 0
                        ),
                        2,
                    ),
                },
                "stats": {
                    "total_folders": total_folders,
                    "total_files": total_files,
                },
            }
        )


# Resource Request Views
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import ResourceRequest
from .serializers import ResourceListSerializer, ResourceRequestSerializer, ResourceRequestCreateSerializer

class CreateResourceRequestView(generics.CreateAPIView):
    """Create a new resource request."""
    permission_classes = [IsAuthenticated]
    serializer_class = ResourceRequestCreateSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get academic context from user profile
        user_profile = getattr(request.user, 'profile', None)
        
        resource_request = ResourceRequest.objects.create(
            title=serializer.validated_data.get('title'),
            description=serializer.validated_data.get('description'),
            requested_by=request.user,
            course=serializer.validated_data.get('course'),
            faculty=serializer.validated_data.get('faculty') or (user_profile.faculty if user_profile else None),
            department=serializer.validated_data.get('department'),
            priority=serializer.validated_data.get('priority', 'medium'),
        )
        
        return Response({
            'id': str(resource_request.id),
            'title': resource_request.title,
            'status': resource_request.status,
            'message': 'Resource request created successfully'
        }, status=status.HTTP_201_CREATED)


class ListResourceRequestsView(generics.ListAPIView):
    """List resource requests."""
    permission_classes = [IsAuthenticated]
    serializer_class = ResourceRequestSerializer
    queryset = ResourceRequest.objects.none()
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ResourceRequest.objects.none()

        user = self.request.user
        status_filter = self.request.query_params.get('status')
        
        queryset = ResourceRequest.objects.all()
        
        # Non-admin users can see their own requests plus community requests in scope
        if not user.is_staff and not user.is_superuser:
            scope_filter = models.Q()
            if getattr(user, "course_id", None):
                scope_filter |= models.Q(course_id=user.course_id)
            if getattr(user, "department_id", None):
                scope_filter |= models.Q(department_id=user.department_id)
            if getattr(user, "faculty_id", None):
                scope_filter |= models.Q(faculty_id=user.faculty_id)

            community_filter = models.Q(status="pending")
            if scope_filter:
                community_filter &= scope_filter

            queryset = queryset.filter(models.Q(requested_by=user) | community_filter)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-priority', '-created_at')


class UpvoteResourceRequestView(generics.CreateAPIView):
    """Upvote a resource request."""
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        request_id = kwargs.get('request_id')
        try:
            resource_request = ResourceRequest.objects.get(id=request_id)
        except ResourceRequest.DoesNotExist:
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user already upvoted
        if request.user in resource_request.requested_by_upvoted.all():
            resource_request.cancel_upvote(request.user)
            return Response({
                'upvotes': resource_request.upvotes,
                'upvoted': False,
                'message': 'Upvote removed'
            })
        else:
            resource_request.upvote(request.user)
            return Response({
                'upvotes': resource_request.upvotes,
                'upvoted': True,
                'message': 'Upvoted successfully'
            })


# Course Progress Views
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import models

class CourseProgressListView(generics.ListAPIView):
    """List all course progress for current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = CourseProgressSerializer
    
    def get_queryset(self):
        from .models import CourseProgress
        return CourseProgress.objects.filter(
            user=self.request.user
        ).select_related('course', 'resource').order_by('-last_accessed')


class CourseProgressDetailView(generics.RetrieveUpdateAPIView):
    """Get or update progress for a specific course."""
    permission_classes = [IsAuthenticated]
    serializer_class = CourseProgressSerializer
    
    def get_queryset(self):
        from .models import CourseProgress
        return CourseProgress.objects.filter(user=self.request.user)
    
    def update(self, request, *args, **kwargs):
        from .models import CourseProgress
        
        instance = self.get_object()
        new_status = request.data.get('status')
        
        if new_status == 'completed':
            instance.mark_completed()
        elif new_status == 'in_progress':
            instance.mark_in_progress()
        
        return Response({
            'status': instance.status,
            'completion_percentage': instance.completion_percentage,
            'time_spent_minutes': instance.time_spent_minutes,
        })


class UpdateResourceProgressView(generics.CreateAPIView):
    """Update progress for a specific resource in a course."""
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        from .models import CourseProgress
        from django.utils import timezone
        
        course_id = request.data.get('course_id')
        resource_id = request.data.get('resource_id')
        action = request.data.get('action', 'view')  # view, start, complete
        time_spent = int(request.data.get('time_spent_minutes', 0))
        
        # Get or create progress record
        progress, created = CourseProgress.objects.get_or_create(
            user=request.user,
            course_id=course_id,
            resource_id=resource_id,
            defaults={'status': 'not_started'}
        )
        
        if action == 'start':
            if progress.status != 'completed':
                progress.mark_in_progress()
            else:
                progress.last_accessed = timezone.now()
                progress.save(update_fields=['last_accessed', 'updated_at'])
        elif action == 'complete':
            progress.mark_completed()
        elif action == 'view':
            if progress.status == 'not_started':
                progress.mark_in_progress()
            else:
                progress.last_accessed = timezone.now()
                progress.save(update_fields=['last_accessed', 'updated_at'])
        
        if time_spent > 0:
            progress.update_time_spent(time_spent)
        
        return Response({
            'progress_id': str(progress.id),
            'status': progress.status,
            'completion_percentage': progress.completion_percentage,
            'time_spent_minutes': progress.time_spent_minutes,
        })


class CourseOverallProgressView(generics.ListAPIView):
    """Get overall progress for a specific course."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        course_id = kwargs.get('course_id')

        try:
            from apps.courses.models import Course

            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(CourseProgressService.build_course_summary(request.user, course))


class CourseProgressSummaryListView(APIView):
    """Return aggregated progress summaries for the current user's courses."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="api_courses_progress_list",
        summary="List user's course progress summaries",
        description="Returns aggregated progress summaries for all courses the user is enrolled in.",
    )
    def get(self, request):
        from apps.courses.models import Course
        from apps.activity.models import ActivityType, RecentActivity
        from apps.downloads.models import Download
        from .models import CourseProgress

        course_ids = set()
        if getattr(request.user, "course_id", None):
            course_ids.add(request.user.course_id)

        course_ids.update(
            CourseProgress.objects.filter(user=request.user).values_list(
                "course_id", flat=True
            )
        )
        course_ids.update(
            Download.objects.filter(
                user=request.user,
                resource__course__isnull=False,
            ).values_list("resource__course_id", flat=True)
        )
        course_ids.update(
            RecentActivity.objects.filter(
                user=request.user,
                activity_type=ActivityType.VIEWED_RESOURCE,
                resource__course__isnull=False,
            ).values_list("resource__course_id", flat=True)
        )

        courses = Course.objects.filter(id__in=course_ids).order_by("name")
        summaries = [
            CourseProgressService.build_course_summary(request.user, course)
            for course in courses
        ]
        return Response(summaries)


class CourseProgressSummaryUpdateView(APIView):
    """GET a course summary or POST a per-resource progress update."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="api_courses_progress_detail",
        summary="Get or update specific course progress",
        description="GET returns progress summary for a specific course. POST updates per-resource progress.",
    )
    def get(self, request, course_id):
        try:
            from apps.courses.models import Course

            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(CourseProgressService.build_course_summary(request.user, course))

    def post(self, request, course_id):
        from django.utils import timezone
        from .models import CourseProgress

        resource_id = request.data.get("resource_id")
        action = request.data.get("action")
        status_value = request.data.get("status")
        time_spent = int(request.data.get("time_spent_minutes", 0) or 0)

        if not resource_id:
            return Response(
                {"detail": "resource_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_action = str(action or status_value or "view").strip().lower()
        progress, _ = CourseProgress.objects.get_or_create(
            user=request.user,
            course_id=course_id,
            resource_id=resource_id,
            defaults={"status": "not_started"},
        )

        if normalized_action in {"start", "in_progress"}:
            if progress.status != "completed":
                progress.mark_in_progress()
            else:
                progress.last_accessed = timezone.now()
                progress.save(update_fields=["last_accessed", "updated_at"])
        elif normalized_action in {"complete", "completed"}:
            progress.mark_completed()
        else:
            if progress.status == "not_started":
                progress.mark_in_progress()
            else:
                progress.last_accessed = timezone.now()
                progress.save(update_fields=["last_accessed", "updated_at"])

        if time_spent > 0:
            progress.update_time_spent(time_spent)

        return Response(
            {
                "progress_id": str(progress.id),
                "status": progress.status,
                "completion_percentage": progress.completion_percentage,
                "time_spent_minutes": progress.time_spent_minutes,
            }
        )
