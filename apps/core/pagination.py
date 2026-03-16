"""
Pagination classes for CampusHub.
"""

from rest_framework.pagination import (CursorPagination, LimitOffsetPagination,
                                       PageNumberPagination)
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """
    Standard pagination for most endpoints.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"


class StandardResultsSetPagination(StandardPagination):
    """
    Backward-compatible alias used across multiple modules.
    """


class LargePagination(PageNumberPagination):
    """
    Pagination for endpoints with large datasets.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"


class SmallPagination(PageNumberPagination):
    """
    Pagination for endpoints with small datasets.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50
    page_query_param = "page"


class InfiniteScrollPagination(LimitOffsetPagination):
    """
    Pagination for infinite scroll functionality.
    """

    default_limit = 20
    max_limit = 100
    limit_query_param = "limit"
    offset_query_param = "offset"


class CursorSetPagination(CursorPagination):
    """
    Cursor-based pagination for very large datasets.
    """

    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"


class PaginationHandlerMixin:
    """
    Mixin to add pagination to generic views.
    """

    pagination_class = StandardPagination

    def get_pagination_class(self):
        """Get pagination class based on view."""
        return getattr(self, "pagination_class", StandardPagination)

    def paginate_queryset(self, queryset):
        """Paginate the queryset."""
        paginator = self.get_pagination_class()()
        return paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """Return paginated response."""
        paginator = self.get_pagination_class()()
        return paginator.get_paginated_response(data)


class EnhancedPageNumberPagination(PageNumberPagination):
    """
    Enhanced pagination with additional metadata.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """Return enhanced paginated response."""
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "current_page": self.page.number,
                "total_pages": self.page.paginator.num_pages,
                "page_size": self.page_size,
                "results": data,
            }
        )


class NoPagination(PageNumberPagination):
    """
    Disable pagination.
    """

    page_size = None
    page_size_query_param = None
