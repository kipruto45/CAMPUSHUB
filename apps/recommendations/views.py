"""
Views for Recommendation Module.
"""

from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.recommendations.serializers import (PopularResourceSerializer,
                                              RecommendedResourceSerializer,
                                              RelatedResourceSerializer,
                                              TrendingResourceSerializer)
from apps.resources.serializers import ResourceListSerializer
from apps.recommendations.services import (get_collaborative_recommendations,
                                           get_content_based_recommendations,
                                           get_course_based_recommendations,
                                           get_download_based_recommendations,
                                           get_for_you_recommendations,
                                           get_hybrid_recommendations,
                                           get_popular_recommendations,
                                           get_related_resources,
                                           get_saved_based_recommendations,
                                           get_seasonal_recommendations,
                                           get_trending_resources)
from apps.resources.models import Resource


def _parse_limit(request, default=10, max_limit=50):
    try:
        value = int(request.query_params.get("limit", default))
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, max_limit))


class ForYouRecommendationsView(generics.ListAPIView):
    """
    Get personalized recommendations for the user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_for_you_recommendations(self.request.user, limit)


class TrendingRecommendationsView(generics.ListAPIView):
    """
    Get trending resources.
    """

    permission_classes = [AllowAny]
    serializer_class = TrendingResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_trending_resources(limit)


class PopularRecommendationsView(generics.ListAPIView):
    """
    Get popular recommendations based on views, downloads, and favorites.

    This endpoint uses a weighted popularity algorithm:
    - View count (0.25 weight)
    - Download count (0.45 weight)
    - Favorite count (0.30 weight)
    - Optional rating (0.10 weight)
    - Recency multiplier (1.20 for 7 days, 1.10 for 30 days)

    Returns resources sorted by recommendation score.
    """

    permission_classes = [AllowAny]
    serializer_class = PopularResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_popular_recommendations(limit)


class RelatedResourcesView(generics.ListAPIView):
    """
    Get resources related to a specific resource.
    """

    permission_classes = [AllowAny]
    serializer_class = RelatedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        resource_id = self.kwargs.get("resource_id")
        limit = _parse_limit(self.request, default=6)

        try:
            resource = Resource.objects.get(id=resource_id, status="approved")
            return get_related_resources(resource, self.request.user, limit)
        except Resource.DoesNotExist:
            return Resource.objects.none()


class CourseBasedRecommendationsView(generics.ListAPIView):
    """
    Get course-based recommendations.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_course_based_recommendations(self.request.user, limit)


class SavedBasedRecommendationsView(generics.ListAPIView):
    """
    Get recommendations based on saved/bookmarked resources.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_saved_based_recommendations(self.request.user, limit)


class DownloadBasedRecommendationsView(generics.ListAPIView):
    """
    Get recommendations based on recent downloads.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_download_based_recommendations(self.request.user, limit)


class ContentBasedRecommendationsView(generics.ListAPIView):
    """
    Get content-based recommendations based on user's interaction history.

    This algorithm recommends resources similar to ones the user has:
    - Downloaded
    - Viewed
    - Bookmarked
    - Favorited
    - Highly rated

    Based on:
    - Tags (3.0 weight)
    - Title (2.0 weight)
    - Description (1.5 weight)
    - Resource type (1.0 weight)
    - Course (2.5 weight)
    - Unit (3.0 weight)
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_content_based_recommendations(self.request.user, limit)


class CollaborativeFilteringView(generics.ListAPIView):
    """
    Get collaborative filtering recommendations.

    This algorithm recommends resources that similar students have downloaded or liked.
    Similarity is based on:
    - Same course (3.0 weight)
    - Same year of study (2.5 weight)
    - Same department (2.0 weight)
    - Same faculty (1.5 weight)

    Process:
    1. Get current user's academic profile
    2. Find similar users (same course/year)
    3. Get resources downloaded/favorited by similar users
    4. Rank by number of similar users who interacted + similarity score
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_collaborative_recommendations(self.request.user, limit)


class HybridRecommendationsView(generics.ListAPIView):
    """
    Get hybrid recommendations combining all signals.

    This algorithm combines 5 recommendation approaches:
    - Popularity (20%): Based on views, downloads, favorites
    - Academic (20%): Matches user's course/year/department
    - Behavior (20%): Based on user's interaction history
    - Content (20%): Similar to resources user interacted with
    - Collaborative (20%): What similar students liked

    Each signal is normalized to 0-1 range before combining.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecommendedResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_hybrid_recommendations(self.request.user, limit)


class SeasonalRecommendationsView(generics.ListAPIView):
    """
    Get time-based/seasonal recommendations based on academic calendar.

    This algorithm boosts resources relevant to the current academic period:
    - Exam periods (April, May, August, December): Exam papers, questions
    - Project periods (March, September): Projects, assignments
    - Revision periods (January, June, November): Notes, summaries
    - Beginning (February, July): Introductory materials

    Reasons returned:
    - "Essential for exam preparation"
    - "Great for your project work"
    - "Perfect for revision"
    - "Start the semester right"
    """

    permission_classes = [AllowAny]
    serializer_class = PopularResourceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        limit = _parse_limit(self.request, default=10)
        return get_seasonal_recommendations(limit)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_recommendations(request):
    """
    Get all recommendation types for dashboard display.
    """
    limit = _parse_limit(request, default=5, max_limit=20)

    for_you = get_for_you_recommendations(request.user, limit)
    trending = get_trending_resources(limit)
    popular = get_popular_recommendations(limit)
    download_based = get_download_based_recommendations(request.user, limit)

    return Response(
        {
            "for_you": RecommendedResourceSerializer(
                for_you, many=True, context={"request": request}
            ).data,
            "trending": TrendingResourceSerializer(
                trending, many=True, context={"request": request}
            ).data,
            "popular": PopularResourceSerializer(popular, many=True).data,
            "download_based": RecommendedResourceSerializer(
                download_based, many=True, context={"request": request}
            ).data,
        }
    )


class AIStudyPlanView(generics.ListAPIView):
    """
    AI-powered study plan recommendations based on user's learning progress.
    """
    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticated]
    queryset = Resource.objects.none()

    def get_queryset(self):
        from .services import get_ai_study_plan_recommendations
        user = self.request.user
        limit = int(self.request.query_params.get('limit', 10))
        recommendations = get_ai_study_plan_recommendations(user, limit=limit)
        return recommendations


class DifficultyAnalysisView(generics.ListAPIView):
    """
    Resources with difficulty analysis based on engagement metrics.
    """
    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticated]
    queryset = Resource.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        from .services import get_difficulty_analyzed_recommendations
        user = self.request.user
        limit = int(self.request.query_params.get('limit', 10))
        return get_difficulty_analyzed_recommendations(user, limit=limit)


class LearningPathView(generics.ListAPIView):
    """
    Learning path recommendations for specific topics.
    """
    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticated]
    queryset = Resource.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        from .services import get_learning_path_recommendations
        topic = self.request.query_params.get('topic', '')
        if not topic:
            return Resource.objects.none()
        limit = int(self.request.query_params.get('limit', 10))
        return get_learning_path_recommendations(self.request.user, topic, limit=limit)
