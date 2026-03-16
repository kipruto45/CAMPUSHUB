"""Services for bookmark operations."""

from rest_framework.exceptions import ValidationError

from apps.accounts.models import Profile
from apps.resources.models import Resource

from .models import Bookmark


class BookmarkService:
    """Business logic for bookmark workflows."""

    @staticmethod
    def _is_staff(user) -> bool:
        """Support both normalized and legacy lowercase role values."""
        role = str(getattr(user, "role", "")).upper()
        return bool(
            getattr(user, "is_superuser", False) or role in {"ADMIN", "MODERATOR"}
        )

    @staticmethod
    def is_resource_bookmarkable(user, resource: Resource) -> bool:
        """Check whether a user can bookmark a resource."""
        if resource.status == "approved" and resource.is_public:
            return True
        if resource.uploaded_by_id == user.id:
            return True
        if BookmarkService._is_staff(user):
            return True
        return False

    @staticmethod
    def validate_resource_bookmarkable(user, resource: Resource):
        """Raise validation error if resource cannot be bookmarked by user."""
        if not BookmarkService.is_resource_bookmarkable(user, resource):
            raise ValidationError(
                {"resource": "Resource is not available for bookmarking."}
            )

    @staticmethod
    def add_bookmark(user, resource: Resource) -> Bookmark:
        """Create a bookmark if it does not already exist.
        
        This method is idempotent - if the bookmark already exists, it returns
        the existing bookmark without raising an error. This makes it safe for
        offline sync replay.
        """
        BookmarkService.validate_resource_bookmarkable(user, resource)
        bookmark, created = Bookmark.objects.get_or_create(user=user, resource=resource)
        # Idempotent: return existing bookmark without error if already exists
        return bookmark

    @staticmethod
    def remove_bookmark(user, *, resource: Resource = None, bookmark: Bookmark = None):
        """Remove an existing bookmark for the user.
        
        This method is idempotent - if the bookmark doesn't exist, it returns
        without raising an error. This makes it safe for offline sync replay.
        """
        if bookmark is None and resource is None:
            raise ValidationError("Bookmark target is required.")

        queryset = Bookmark.objects.filter(user=user)
        if bookmark is not None:
            queryset = queryset.filter(id=bookmark.id)
        if resource is not None:
            queryset = queryset.filter(resource=resource)

        deleted_count, _ = queryset.delete()
        # Idempotent: don't raise error if bookmark doesn't exist

    @staticmethod
    def toggle_bookmark(user, resource: Resource) -> dict:
        """Toggle bookmark state and return the new state."""
        BookmarkService.validate_resource_bookmarkable(user, resource)
        existing = Bookmark.objects.filter(user=user, resource=resource).first()
        if existing:
            existing.delete()
            return {
                "is_bookmarked": False,
                "bookmark_id": None,
                "message": "Bookmark removed.",
            }

        bookmark = Bookmark.objects.create(user=user, resource=resource)
        return {
            "is_bookmarked": True,
            "bookmark_id": str(bookmark.id),
            "message": "Resource bookmarked.",
        }

    @staticmethod
    def get_user_bookmarks(
        user, *, resource_type=None, course_id=None, unit_id=None, sort="newest"
    ):
        """Get user bookmarks with visibility rules, filtering and sorting."""
        queryset = Bookmark.objects.filter(user=user).select_related(
            "resource",
            "resource__course",
            "resource__unit",
        )

        if not BookmarkService._is_staff(user):
            queryset = queryset.filter(
                resource__status="approved", resource__is_public=True
            )

        if resource_type:
            queryset = queryset.filter(resource__resource_type=resource_type)
        if course_id:
            queryset = queryset.filter(resource__course_id=course_id)
        if unit_id:
            queryset = queryset.filter(resource__unit_id=unit_id)

        sort_map = {
            "newest": "-created_at",
            "oldest": "created_at",
            "title": "resource__title",
            "rating": "-resource__average_rating",
            "upload_date": "-resource__created_at",
            "resource_type": "resource__resource_type",
        }
        return queryset.order_by(sort_map.get(sort, "-created_at"))

    @staticmethod
    def get_recent_bookmarks(user, limit=20):
        """Get recent bookmarks for a user."""
        return BookmarkService.get_user_bookmarks(user)[:limit]

    @staticmethod
    def recalculate_user_bookmark_count(user):
        """Update denormalized bookmark count on profile."""
        profile, _ = Profile.objects.get_or_create(user=user)
        count = Bookmark.objects.filter(user=user).count()
        if profile.total_bookmarks != count:
            profile.total_bookmarks = count
            profile.save(update_fields=["total_bookmarks"])
