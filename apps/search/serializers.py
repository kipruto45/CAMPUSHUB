"""Serializers for search endpoints."""

from rest_framework import serializers

from apps.search.models import RecentSearch


class SearchSuggestionSerializer(serializers.Serializer):
    """Structured search suggestion row."""

    value = serializers.CharField()
    type = serializers.ChoiceField(
        choices=["title", "course", "unit", "tag", "recent"],
    )


class RecentSearchSerializer(serializers.ModelSerializer):
    """Recent search serializer."""

    class Meta:
        model = RecentSearch
        fields = [
            "id",
            "query",
            "normalized_query",
            "filters",
            "results_count",
            "last_searched_at",
        ]
        read_only_fields = fields
