"""
Business logic services for favorites app.
"""

from django.db import IntegrityError
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.resources.models import PersonalFolder, PersonalResource, Resource

from .models import Favorite, FavoriteType


class FavoriteService:
    """Service for handling favorite operations."""

    @staticmethod
    def validate_resource_favoritable(resource: Resource):
        """Ensure resource favorites only target approved public resources."""
        if resource.status != "approved" or not resource.is_public:
            raise ValidationError(
                {"resource": "Resource is not available for favorites."}
            )

    @staticmethod
    def _validate_target(
        user,
        favorite_type,
        resource=None,
        personal_file=None,
        personal_folder=None,
    ):
        provided_targets = [resource is not None, personal_file is not None, personal_folder is not None]
        if sum(provided_targets) != 1:
            raise ValidationError(
                "Exactly one target is required for a favorite operation."
            )

        if favorite_type == FavoriteType.RESOURCE:
            if resource is None:
                raise ValidationError({"resource": "resource_id is required."})
            FavoriteService.validate_resource_favoritable(resource)
        elif favorite_type == FavoriteType.PERSONAL_FILE:
            if personal_file is None:
                raise ValidationError({"personal_file": "personal_file_id is required."})
            if personal_file.user_id != user.id:
                raise ValidationError(
                    {"personal_file": "You can only favorite your own files."}
                )
        elif favorite_type == FavoriteType.FOLDER:
            if personal_folder is None:
                raise ValidationError({"personal_folder": "personal_folder_id is required."})
            if personal_folder.user_id != user.id:
                raise ValidationError(
                    {"personal_folder": "You can only favorite your own folders."}
                )
        else:
            raise ValidationError({"favorite_type": "Invalid favorite type."})

    @staticmethod
    def resolve_target(
        *,
        user,
        favorite_type,
        resource_id=None,
        personal_file_id=None,
        personal_folder_id=None,
    ) -> tuple[Resource | None, PersonalResource | None, PersonalFolder | None]:
        """Resolve and validate favorite target objects from IDs."""
        resource = None
        personal_file = None
        personal_folder = None

        if favorite_type == FavoriteType.RESOURCE:
            if not resource_id:
                raise ValidationError({"resource_id": "resource_id is required."})
            try:
                resource = Resource.objects.get(id=resource_id)
            except Resource.DoesNotExist as exc:
                raise ValidationError({"resource_id": "Resource not found."}) from exc
        elif favorite_type == FavoriteType.PERSONAL_FILE:
            if not personal_file_id:
                raise ValidationError(
                    {"personal_file_id": "personal_file_id is required."}
                )
            try:
                personal_file = PersonalResource.objects.get(id=personal_file_id, user=user)
            except PersonalResource.DoesNotExist as exc:
                raise ValidationError(
                    {"personal_file_id": "Personal file not found."}
                ) from exc
        elif favorite_type == FavoriteType.FOLDER:
            if not personal_folder_id:
                raise ValidationError(
                    {"personal_folder_id": "personal_folder_id is required."}
                )
            try:
                personal_folder = PersonalFolder.objects.get(id=personal_folder_id, user=user)
            except PersonalFolder.DoesNotExist as exc:
                raise ValidationError(
                    {"personal_folder_id": "Personal folder not found."}
                ) from exc
        else:
            raise ValidationError({"favorite_type": "Invalid favorite type."})

        FavoriteService._validate_target(
            user=user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )
        return resource, personal_file, personal_folder

    @staticmethod
    def add_favorite(
        user, favorite_type, resource=None, personal_file=None, personal_folder=None
    ):
        """
        Add an item to favorites.

        Args:
            user: The user adding to favorites
            favorite_type: Type of favorite (resource, personal_file, folder)
            resource: Optional Resource object
            personal_file: Optional PersonalResource object
            personal_folder: Optional PersonalFolder object

        Returns:
            tuple: (Favorite object or None, bool is_new)
        """
        FavoriteService._validate_target(
            user=user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )
        try:
            favorite = Favorite.objects.create(
                user=user,
                favorite_type=favorite_type,
                resource=resource,
                personal_file=personal_file,
                personal_folder=personal_folder,
            )
            return favorite, True
        except IntegrityError:
            # Already favorited
            return None, False

    @staticmethod
    def remove_favorite(
        user, favorite_type, resource=None, personal_file=None, personal_folder=None
    ):
        """
        Remove an item from favorites.

        Args:
            user: The user removing from favorites
            favorite_type: Type of favorite
            resource: Optional Resource object
            personal_file: Optional PersonalResource object
            personal_folder: Optional PersonalFolder object

        Returns:
            bool: True if removed, False if not found
        """
        filters = {
            "user": user,
            "favorite_type": favorite_type,
        }

        if resource:
            filters["resource"] = resource
        elif personal_file:
            filters["personal_file"] = personal_file
        elif personal_folder:
            filters["personal_folder"] = personal_folder

        deleted, _ = Favorite.objects.filter(**filters).delete()
        return deleted > 0

    @staticmethod
    def toggle_favorite(
        user, favorite_type, resource=None, personal_file=None, personal_folder=None
    ):
        """
        Toggle favorite status.

        Args:
            user: The user toggling favorite
            favorite_type: Type of favorite
            resource: Optional Resource object
            personal_file: Optional PersonalResource object
            personal_folder: Optional PersonalFolder object

        Returns:
            dict: Result with is_favorited status and message
        """
        FavoriteService._validate_target(
            user=user,
            favorite_type=favorite_type,
            resource=resource,
            personal_file=personal_file,
            personal_folder=personal_folder,
        )

        filters = {
            "user": user,
            "favorite_type": favorite_type,
        }

        if resource:
            filters["resource"] = resource
        elif personal_file:
            filters["personal_file"] = personal_file
        elif personal_folder:
            filters["personal_folder"] = personal_folder

        existing = Favorite.objects.filter(**filters).first()

        if existing:
            existing.delete()
            return {"is_favorited": False, "message": "Removed from favorites."}
        else:
            try:
                Favorite.objects.create(
                    user=user,
                    favorite_type=favorite_type,
                    resource=resource,
                    personal_file=personal_file,
                    personal_folder=personal_folder,
                )
                return {"is_favorited": True, "message": "Added to favorites."}
            except IntegrityError:
                return {"is_favorited": True, "message": "Already in favorites."}

    @staticmethod
    def get_user_favorites(user, favorite_type=None, limit=None):
        """
        Get user's favorites.

        Args:
            user: The user to get favorites for
            favorite_type: Optional filter by type
            limit: Optional limit

        Returns:
            QuerySet: User's favorites
        """
        queryset = Favorite.objects.filter(user=user).select_related(
            "resource",
            "resource__course",
            "resource__unit",
            "personal_file",
            "personal_folder",
        )

        if favorite_type:
            queryset = queryset.filter(favorite_type=favorite_type)

        # Hide resource favorites that are no longer publicly visible.
        queryset = queryset.filter(
            Q(favorite_type=FavoriteType.RESOURCE, resource__status="approved", resource__is_public=True)
            | ~Q(favorite_type=FavoriteType.RESOURCE)
        )

        if limit:
            return queryset[:limit]
        return queryset

    @staticmethod
    def is_favorited(user, resource=None, personal_file=None, personal_folder=None):
        """
        Check if an item is favorited by user.

        Args:
            user: The user to check
            resource: Optional Resource
            personal_file: Optional PersonalResource
            personal_folder: Optional PersonalFolder

        Returns:
            bool: True if favorited
        """
        filters = {"user": user}

        if resource:
            filters["resource"] = resource
        elif personal_file:
            filters["personal_file"] = personal_file
        elif personal_folder:
            filters["personal_folder"] = personal_folder

        return Favorite.objects.filter(**filters).exists()

    @staticmethod
    def get_favorite_stats(user):
        """
        Get favorite statistics for a user.

        Args:
            user: The user to get stats for

        Returns:
            dict: Statistics
        """
        return {
            "total_favorites": Favorite.objects.filter(user=user).count(),
            "resource_count": Favorite.objects.filter(
                user=user, favorite_type=FavoriteType.RESOURCE
            ).count(),
            "personal_file_count": Favorite.objects.filter(
                user=user, favorite_type=FavoriteType.PERSONAL_FILE
            ).count(),
            "folder_count": Favorite.objects.filter(
                user=user, favorite_type=FavoriteType.FOLDER
            ).count(),
        }
