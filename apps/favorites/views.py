"""
Views for favorites app.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination
from apps.resources.models import PersonalFolder, PersonalResource, Resource

from .models import Favorite, FavoriteType
from .serializers import (FavoriteCreateSerializer, FavoriteListSerializer,
                          FavoriteStatsSerializer, FavoriteToggleSerializer)
from .services import FavoriteService


class FavoriteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet for listing/creating/deleting favorites."""

    serializer_class = FavoriteListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Favorite.objects.none()
        requested_type = self.request.query_params.get("type")
        type_aliases = {
            "resources": FavoriteType.RESOURCE,
            "resource": FavoriteType.RESOURCE,
            "files": FavoriteType.PERSONAL_FILE,
            "file": FavoriteType.PERSONAL_FILE,
            "folders": FavoriteType.FOLDER,
            "folder": FavoriteType.FOLDER,
            FavoriteType.RESOURCE: FavoriteType.RESOURCE,
            FavoriteType.PERSONAL_FILE: FavoriteType.PERSONAL_FILE,
            FavoriteType.FOLDER: FavoriteType.FOLDER,
        }
        favorite_type = type_aliases.get(str(requested_type or "").lower())
        return FavoriteService.get_user_favorites(
            self.request.user, favorite_type=favorite_type
        )

    def get_serializer_class(self):
        if self.action == "create":
            return FavoriteCreateSerializer
        return FavoriteListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        favorite_type = data["favorite_type"]
        resource, personal_file, personal_folder = FavoriteService.resolve_target(
            user=request.user,
            favorite_type=favorite_type,
            resource_id=data.get("resource_id"),
            personal_file_id=data.get("personal_file_id"),
            personal_folder_id=data.get("personal_folder_id"),
        )

        favorite, is_new = FavoriteService.add_favorite(
            user=request.user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )

        if not is_new:
            return Response(
                {"detail": "Already in favorites."}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            FavoriteListSerializer(favorite).data, status=status.HTTP_201_CREATED
        )


class FavoriteCreateView(generics.CreateAPIView):
    """View for creating a favorite."""

    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        favorite_type = data["favorite_type"]
        resource, personal_file, personal_folder = FavoriteService.resolve_target(
            user=request.user,
            favorite_type=favorite_type,
            resource_id=data.get("resource_id"),
            personal_file_id=data.get("personal_file_id"),
            personal_folder_id=data.get("personal_folder_id"),
        )

        favorite, is_new = FavoriteService.add_favorite(
            user=request.user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )

        if not is_new:
            return Response(
                {"detail": "Already in favorites."}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            FavoriteListSerializer(favorite).data, status=status.HTTP_201_CREATED
        )


class FavoriteDeleteView(generics.DestroyAPIView):
    """View for deleting a favorite."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)


class FavoriteToggleView(generics.CreateAPIView):
    """View for toggling favorite status."""

    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteToggleSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        favorite_type = (
            FavoriteType.RESOURCE
            if data.get("resource_id")
            else FavoriteType.PERSONAL_FILE
            if data.get("personal_file_id")
            else FavoriteType.FOLDER
        )
        resource, personal_file, personal_folder = FavoriteService.resolve_target(
            user=request.user,
            favorite_type=favorite_type,
            resource_id=data.get("resource_id"),
            personal_file_id=data.get("personal_file_id"),
            personal_folder_id=data.get("personal_folder_id"),
        )

        result = FavoriteService.toggle_favorite(
            user=request.user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )

        return Response(result)


class FavoriteStatsView(generics.RetrieveAPIView):
    """View for favorite statistics."""

    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteStatsSerializer

    def retrieve(self, request, *args, **kwargs):
        stats = FavoriteService.get_favorite_stats(request.user)
        serializer = self.get_serializer(stats)
        return Response(serializer.data)


class ResourceFavoriteToggleView(generics.CreateAPIView):
    """Toggle favorite status for a resource."""

    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        resource = get_object_or_404(Resource, id=resource_id)
        result = FavoriteService.toggle_favorite(
            user=request.user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )

        return Response(result)


class PersonalFileFavoriteToggleView(generics.CreateAPIView):
    """Toggle favorite status for a personal file."""

    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        file_id = kwargs.get("file_id")

        personal_file = get_object_or_404(PersonalResource, id=file_id, user=request.user)

        result = FavoriteService.toggle_favorite(
            user=request.user,
            favorite_type=FavoriteType.PERSONAL_FILE,
            personal_file=personal_file,
        )

        return Response(result)


class FolderFavoriteToggleView(generics.CreateAPIView):
    """Toggle favorite status for a folder."""

    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        folder_id = kwargs.get("folder_id")

        folder = get_object_or_404(PersonalFolder, id=folder_id, user=request.user)

        result = FavoriteService.toggle_favorite(
            user=request.user, favorite_type=FavoriteType.FOLDER, personal_folder=folder
        )

        return Response(result)
