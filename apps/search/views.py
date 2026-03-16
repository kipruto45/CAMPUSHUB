"""Views for search app."""

from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.resources.models import PersonalResource, Resource
from apps.resources.serializers import ResourceListSerializer
from apps.search.models import RecentSearch
from apps.search.serializers import RecentSearchSerializer, SearchSuggestionSerializer

from .services import SearchService


class SearchView(generics.ListAPIView):
    """Search approved public resources with filters, ranking and sorting."""

    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _extract_filters(self) -> dict:
        params = self.request.query_params
        filters = {
            "resource_type": params.get("resource_type"),
            "faculty": params.get("faculty"),
            "department": params.get("department"),
            "course": params.get("course"),
            "unit": params.get("unit"),
            "semester": params.get("semester"),
            "year_of_study": params.get("year_of_study") or params.get("year"),
            "file_type": params.get("file_type"),
        }
        return {key: value for key, value in filters.items() if value not in (None, "")}

    def get_queryset(self):
        query = self.request.query_params.get(
            "q", self.request.query_params.get("search", "")
        )
        sort = self.request.query_params.get("sort", "")
        filters = self._extract_filters()

        self._search_query = query
        self._search_filters = filters
        return SearchService.search_resources(
            query=query,
            filters=filters,
            user=self.request.user,
            sort=sort,
        )

    def list(self, request, *args, **kwargs):
        cache_key = None
        if not request.user.is_authenticated:
            cache_key = f"search:list:{request.get_full_path()}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        queryset = self.get_queryset()
        query = getattr(self, "_search_query", "")
        filters = getattr(self, "_search_filters", {})
        if query and request.user.is_authenticated:
            SearchService.save_recent_search(
                request.user,
                query=query,
                filters=filters,
                results_count=queryset.count(),
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"request": request})
            response = self.get_paginated_response(serializer.data)
            if cache_key is not None:
                cache.set(cache_key, response.data, 60)
            return response

        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        response = Response(serializer.data)
        if cache_key is not None:
            cache.set(cache_key, response.data, 60)
        return response


class PersonalSearchView(generics.ListAPIView):
    """Search personal library files."""

    from apps.resources.serializers import PersonalResourceListSerializer

    serializer_class = PersonalResourceListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalResource.objects.none()
        query = self.request.query_params.get("q", "")
        return SearchService.search_personal_files(query, self.request.user)


class SearchSuggestionsView(generics.ListAPIView):
    """Get typed search suggestions."""

    queryset = Resource.objects.none()
    serializer_class = SearchSuggestionSerializer

    def list(self, request, *args, **kwargs):
        query = request.query_params.get("q", "")
        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10

        cache_key = f"search:suggestions:{request.get_full_path()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        typed_suggestions = SearchService.build_search_suggestions(
            query,
            user=request.user if request.user.is_authenticated else None,
            limit=max(1, min(limit, 50)),
        )
        serializer = self.get_serializer(typed_suggestions, many=True)
        response = Response(
            {
                "suggestions": [item["value"] for item in typed_suggestions],
                "typed_suggestions": serializer.data,
            }
        )
        cache.set(cache_key, response.data, 60)
        return response


class RecentSearchesView(generics.ListAPIView):
    """Get and clear the authenticated user's recent searches."""

    permission_classes = [IsAuthenticated]
    queryset = RecentSearch.objects.none()
    serializer_class = RecentSearchSerializer

    def list(self, request, *args, **kwargs):
        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10
        recent = SearchService.get_recent_searches(
            request.user, limit=max(1, min(limit, 50))
        )
        serializer = self.get_serializer(recent, many=True)
        return Response({"recent_searches": serializer.data})

    @extend_schema(operation_id="api_search_recent_clear_destroy")
    def delete(self, request, *args, **kwargs):
        deleted_count, _ = RecentSearch.objects.filter(user=request.user).delete()
        return Response(
            {
                "message": "Recent searches cleared.",
                "deleted_count": deleted_count,
            }
        )


class RecentSearchDeleteView(generics.DestroyAPIView):
    """Delete a single recent search for the authenticated user."""

    permission_classes = [IsAuthenticated]
    queryset = RecentSearch.objects.none()

    @extend_schema(operation_id="api_search_recent_item_destroy")
    def delete(self, request, *args, **kwargs):
        deleted_count = SearchService.delete_recent_search(
            request.user, recent_search_id=kwargs.get("search_id")
        )
        if not deleted_count:
            return Response(
                {"detail": "Recent search not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"message": "Recent search removed.", "deleted_count": deleted_count}
        )


class TrendingSearchesView(generics.ListAPIView):
    """Get trending search terms."""

    queryset = Resource.objects.none()
    serializer_class = ResourceListSerializer

    def list(self, request, *args, **kwargs):
        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10
        cache_key = f"search:trending:{request.get_full_path()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = Response(
            {
                "trending_searches": list(
                    SearchService.get_trending_searches(limit=max(1, min(limit, 50)))
                )
            }
        )
        cache.set(cache_key, response.data, 300)
        return response
