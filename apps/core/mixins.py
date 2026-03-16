"""
Core mixins for CampusHub.
"""

from django.db.models import F
from rest_framework.response import Response


class IncrementCounterMixin:
    """
    Mixin to increment a counter field on a model.
    """

    def increment_counter(self, instance, field_name):
        """Increment the counter field."""
        Model = instance.__class__
        Model.objects.filter(pk=instance.pk).update(
            **{f"{field_name}": F(field_name) + 1}
        )
        instance.refresh_from_db()


class ViewCountMixin:
    """
    Mixin to track view counts.
    """

    def increment_view_count(self, instance):
        """Increment the view count."""
        self.increment_counter(instance, "view_count")


class DownloadCountMixin:
    """
    Mixin to track download counts.
    """

    def increment_download_count(self, instance):
        """Increment the download count."""
        self.increment_counter(instance, "download_count")


class OwnershipMixin:
    """
    Mixin to check object ownership.
    """

    def is_owner(self, obj, user):
        """Check if the user is the owner of the object."""
        return (
            obj.uploaded_by == user if hasattr(obj, "uploaded_by") else obj.user == user
        )

    def check_ownership(self, obj, user):
        """Raise permission denied if user is not the owner."""
        if not self.is_owner(obj, user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You don't have permission to perform this action.")


class ActorMixin:
    """
    Mixin to get actor from request.
    """

    def get_actor(self, request):
        """Get the current user from the request."""
        return request.user if request.user.is_authenticated else None


class ValidateFileMixin:
    """
    Mixin to validate file uploads.
    """

    ALLOWED_EXTENSIONS = [
        "pdf",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "txt",
        "zip",
        "rar",
    ]
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def validate_file(self, file):
        """Validate file extension and size."""
        import os

        from django.core.exceptions import ValidationError

        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size cannot exceed {self.MAX_FILE_SIZE / (1024 * 1024)}MB"
            )

        # Check file extension
        ext = os.path.splitext(file.name)[1].lower().strip(".")
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )

        return True


class SerializerContextMixin:
    """
    Mixin to add request to serializer context.
    """

    def get_serializer_context(self):
        """Add request to serializer context."""
        context = super().get_serializer_context()
        context["request"] = self.request
        context["user"] = (
            self.request.user if self.request.user.is_authenticated else None
        )
        return context


class RateLimitMixin:
    """
    Mixin to implement rate limiting logic.
    """

    def check_rate_limit(self, request, limit=60, period=3600):
        """Check if the user has exceeded the rate limit."""
        from django.core.cache import cache

        key = f"rate_limit_{request.user.id}_{request.path}"
        requests = cache.get(key, 0)

        if requests >= limit:
            from rest_framework.exceptions import Throttled

            raise Throttled()

        cache.set(key, requests + 1, period)
        return True


class DisableForCSRFMixin:
    """
    Mixin to disable CSRF for certain endpoints.
    """

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["skip_csrf"] = True
        return context


class PaginatedResponseMixin:
    """
    Mixin to generate paginated response.
    """

    def paginate_queryset(self, queryset):
        """Paginate the queryset."""
        from rest_framework.pagination import PageNumberPagination

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        if page is not None:
            return paginator.get_paginated_response(page).data
        return queryset

    def get_paginated_response(self, data):
        """Return paginated response."""
        return Response(data)
