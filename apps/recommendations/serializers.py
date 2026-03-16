"""Serializers for recommendation responses."""

from rest_framework import serializers

from apps.resources.models import Resource


class RecommendedResourceSerializer(serializers.ModelSerializer):
    """Serializer for personalized recommendation cards."""

    recommendation_reason = serializers.SerializerMethodField()
    course_name = serializers.CharField(source="course.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    score = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "file_type",
            "resource_type",
            "faculty",
            "department",
            "course",
            "course_name",
            "unit",
            "unit_name",
            "semester",
            "year_of_study",
            "download_count",
            "view_count",
            "average_rating",
            "recommendation_reason",
            "score",
            "created_at",
        ]

    def get_recommendation_reason(self, obj) -> str:
        from apps.recommendations.services import get_recommendation_reason

        request = self.context.get("request")
        user = getattr(request, "user", None)
        return get_recommendation_reason(obj, user)

    def get_score(self, obj) -> float | None:
        for attr in [
            "final_score",
            "hybrid_score",
            "personal_score",
            "trending_score",
            "course_match_score",
            "related_score",
        ]:
            score = getattr(obj, attr, None)
            if score is not None:
                return round(float(score), 4)
        return None


class TrendingResourceSerializer(RecommendedResourceSerializer):
    """Serializer for trending resources."""


class RelatedResourceSerializer(RecommendedResourceSerializer):
    """Serializer for related-resource results."""

    class Meta(RecommendedResourceSerializer.Meta):
        ref_name = "RecommendationRelatedResource"


class PopularResourceSerializer(serializers.ModelSerializer):
    """
    Serializer for popularity-based recommendations.

    Returns resources ranked by:
    - View count (0.25 weight)
    - Download count (0.45 weight)
    - Favorite count (0.30 weight)
    - Optional rating (0.10 weight)
    - Recency multiplier
    """

    recommendation_reason = serializers.SerializerMethodField()
    recommendation_score = serializers.SerializerMethodField()
    favorite_count = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "resource_type",
            "file_type",
            "view_count",
            "download_count",
            "favorite_count",
            "average_rating",
            "recommendation_score",
            "recommendation_reason",
            "created_at",
        ]

    def get_recommendation_reason(self, obj) -> str:
        # Use the reason set by the service
        return getattr(obj, "recommendation_reason", "Popular resource on the platform")

    def get_recommendation_score(self, obj) -> float | None:
        return getattr(obj, "popularity_score", None)

    def get_favorite_count(self, obj) -> int:
        return getattr(obj, "favorite_count", 0) or 0
