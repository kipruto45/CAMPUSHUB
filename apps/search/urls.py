"""
URL configuration for search app.
"""

from django.urls import path

from .views import (PersonalSearchView, RecentSearchDeleteView,
                    RecentSearchesView, SearchSuggestionsView, SearchView,
                    TrendingSearchesView)

app_name = "search"

urlpatterns = [
    path("", SearchView.as_view(), name="search"),
    path("suggestions/", SearchSuggestionsView.as_view(), name="search-suggestions"),
    path("personal/", PersonalSearchView.as_view(), name="search-personal"),
    path("trending/", TrendingSearchesView.as_view(), name="search-trending"),
    path("recent/", RecentSearchesView.as_view(), name="search-recent"),
    path(
        "recent/<uuid:search_id>/",
        RecentSearchDeleteView.as_view(),
        name="search-recent-delete",
    ),
]
