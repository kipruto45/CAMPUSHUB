"""OOP recommendation strategy services for CampusHub.

Demonstrates:
- Abstraction via `BaseRecommender`
- Polymorphism across recommender strategies
- Strategy + Factory patterns in `RecommendationService`
- Set/dict based deduplication and weighted ranking
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict

from django.db.models import Avg, Count, Q

from apps.core.algorithms import (calculate_recommendation_score,
                                  calculate_related_resource_similarity,
                                  deduplicate_resources)


class BaseRecommender(ABC):
    """Common interface for all recommendation strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def recommend(self, user, limit: int = 10, exclude_ids: set | None = None) -> list:
        raise NotImplementedError

    def _base_queryset(self):
        from apps.resources.models import Resource

        return Resource.objects.filter(
            status="approved", is_public=True
        ).select_related(
            "faculty",
            "department",
            "course",
            "unit",
            "uploaded_by",
        )

    def _annotate(self, queryset):
        from apps.favorites.models import FavoriteType

        return queryset.annotate(
            bookmark_count=Count("bookmarks", distinct=True),
            favorite_count=Count(
                "favorites",
                filter=Q(favorites__favorite_type=FavoriteType.RESOURCE),
                distinct=True,
            ),
            rating_avg=Avg("ratings__value"),
        )

    @staticmethod
    def _exclusion_set(exclude_ids: set | None = None) -> set:
        return set(exclude_ids or set())


class TrendingRecommender(BaseRecommender):
    """Platform-wide popularity and engagement recommender."""

    @property
    def name(self) -> str:
        return "TrendingRecommender"

    def recommend(self, user, limit: int = 10, exclude_ids: set | None = None) -> list:
        excluded = self._exclusion_set(exclude_ids)
        queryset = self._annotate(self._base_queryset())
        if excluded:
            queryset = queryset.exclude(id__in=excluded)

        ranked = []
        for resource in queryset:
            resource.score = calculate_recommendation_score(resource)
            resource.reason = "Trending among students"
            ranked.append(resource)

        ranked.sort(
            key=lambda item: (
                getattr(item, "score", 0.0),
                getattr(item, "download_count", 0),
                getattr(item, "view_count", 0),
            ),
            reverse=True,
        )
        return ranked[: max(1, limit)]


class CourseBasedRecommender(BaseRecommender):
    """Academic profile matching recommender."""

    @property
    def name(self) -> str:
        return "CourseBasedRecommender"

    def recommend(self, user, limit: int = 10, exclude_ids: set | None = None) -> list:
        if not user or not user.is_authenticated:
            return TrendingRecommender().recommend(
                user, limit=limit, exclude_ids=exclude_ids
            )

        profile = self._user_profile(user)
        excluded = self._exclusion_set(exclude_ids)

        queryset = self._annotate(self._base_queryset())
        if excluded:
            queryset = queryset.exclude(id__in=excluded)

        ranked = []
        for resource in queryset:
            resource.score = calculate_recommendation_score(
                resource, user_profile=profile
            )
            if resource.score <= 0:
                continue
            resource.reason = self._reason(resource, profile)
            ranked.append(resource)

        ranked.sort(
            key=lambda item: (
                getattr(item, "score", 0.0),
                getattr(item, "download_count", 0),
            ),
            reverse=True,
        )
        return ranked[: max(1, limit)]

    @staticmethod
    def _user_profile(user) -> dict:
        profile = {
            "faculty_id": getattr(user, "faculty_id", None),
            "department_id": getattr(user, "department_id", None),
            "course_id": getattr(user, "course_id", None),
            "year_of_study": getattr(user, "year_of_study", None),
            "semester": getattr(user, "semester", None),
        }

        if hasattr(user, "profile") and user.profile:
            profile["faculty_id"] = profile["faculty_id"] or getattr(
                user.profile, "faculty_id", None
            )
            profile["department_id"] = profile["department_id"] or getattr(
                user.profile, "department_id", None
            )
            profile["course_id"] = profile["course_id"] or getattr(
                user.profile, "course_id", None
            )
            profile["year_of_study"] = profile["year_of_study"] or getattr(
                user.profile, "year_of_study", None
            )

        return profile

    @staticmethod
    def _reason(resource, profile) -> str:
        if profile.get("course_id") and profile["course_id"] == resource.course_id:
            return "Matches your course"
        if (
            profile.get("department_id")
            and profile["department_id"] == resource.department_id
        ):
            return "Popular in your department"
        if profile.get("faculty_id") and profile["faculty_id"] == resource.faculty_id:
            return "Popular in your faculty"
        return "Relevant to your academic profile"


class BehaviorBasedRecommender(BaseRecommender):
    """Behavior-driven recommender based on interaction history."""

    @property
    def name(self) -> str:
        return "BehaviorBasedRecommender"

    def recommend(self, user, limit: int = 10, exclude_ids: set | None = None) -> list:
        if not user or not user.is_authenticated:
            return []

        behavior = self._behavior_profile(user)
        excluded = self._exclusion_set(exclude_ids)
        excluded.update(behavior["consumed_ids"])

        queryset = self._annotate(self._base_queryset()).exclude(id__in=excluded)

        # Candidate scoring using related-similarity to consumed resources + profile score
        seed_resources = list(
            self._base_queryset().filter(id__in=list(behavior["consumed_ids"])[:30])
        )

        ranked = []
        for candidate in queryset:
            related_score = 0
            for seed in seed_resources:
                related_score = max(
                    related_score,
                    calculate_related_resource_similarity(seed, candidate),
                )

            candidate.score = calculate_recommendation_score(
                candidate,
                user_profile=behavior["user_profile"],
                behavior=behavior,
            ) + float(related_score)

            if candidate.score <= 0:
                continue
            candidate.reason = "Based on your views, downloads and saved resources"
            ranked.append(candidate)

        ranked.sort(
            key=lambda item: (
                getattr(item, "score", 0.0),
                getattr(item, "download_count", 0),
            ),
            reverse=True,
        )
        return ranked[: max(1, limit)]

    @staticmethod
    def _behavior_profile(user) -> dict:
        from apps.activity.models import ActivityType, RecentActivity
        from apps.bookmarks.models import Bookmark
        from apps.downloads.models import Download
        from apps.favorites.models import Favorite, FavoriteType
        from apps.ratings.models import Rating

        consumed_ids = set(
            Download.objects.filter(user=user, resource__isnull=False).values_list(
                "resource_id", flat=True
            )
        )
        consumed_ids.update(
            Bookmark.objects.filter(user=user, resource__isnull=False).values_list(
                "resource_id", flat=True
            )
        )
        consumed_ids.update(
            Favorite.objects.filter(
                user=user,
                favorite_type=FavoriteType.RESOURCE,
                resource__isnull=False,
            ).values_list("resource_id", flat=True)
        )
        consumed_ids.update(
            Rating.objects.filter(user=user, resource__isnull=False).values_list(
                "resource_id", flat=True
            )
        )
        consumed_ids.update(
            RecentActivity.objects.filter(
                user=user,
                activity_type=ActivityType.VIEWED_RESOURCE,
                resource__isnull=False,
            ).values_list("resource_id", flat=True)
        )

        preferred_courses = set(
            RecentActivity.objects.filter(
                user=user,
                activity_type=ActivityType.VIEWED_RESOURCE,
                resource__course__isnull=False,
            ).values_list("resource__course_id", flat=True)
        )
        preferred_units = set(
            RecentActivity.objects.filter(
                user=user,
                activity_type=ActivityType.VIEWED_RESOURCE,
                resource__unit__isnull=False,
            ).values_list("resource__unit_id", flat=True)
        )

        user_profile = {
            "faculty_id": getattr(user, "faculty_id", None),
            "department_id": getattr(user, "department_id", None),
            "course_id": getattr(user, "course_id", None),
            "year_of_study": getattr(user, "year_of_study", None),
            "semester": getattr(user, "semester", None),
        }

        return {
            "consumed_ids": consumed_ids,
            "preferred_courses": preferred_courses,
            "preferred_units": preferred_units,
            "user_profile": user_profile,
        }


class RecommendationService:
    """Factory + strategy orchestrator for recommender classes."""

    RECOMMENDERS = {
        "trending": TrendingRecommender,
        "course_based": CourseBasedRecommender,
        "behavior": BehaviorBasedRecommender,
    }

    @classmethod
    def get_recommender(cls, recommender_type: str) -> BaseRecommender:
        recommender_cls = cls.RECOMMENDERS.get(recommender_type, TrendingRecommender)
        return recommender_cls()

    @classmethod
    def get_hybrid_recommendations(
        cls, user, limit: int = 10, weights: dict | None = None
    ) -> list:
        """Combine strategies with weighted aggregation and deduplication."""
        if weights is None:
            weights = {"trending": 0.40, "course_based": 0.30, "behavior": 0.30}

        weighted_scores = defaultdict(float)
        resource_map = {}

        for recommender_type, weight in weights.items():
            recommender = cls.get_recommender(recommender_type)
            items = recommender.recommend(user, limit=limit * 2)
            for index, resource in enumerate(items):
                rank_boost = max(0.1, 1.0 - (index * 0.02))
                weighted_scores[resource.id] += (
                    getattr(resource, "score", 0.0) * float(weight) * rank_boost
                )
                resource_map[resource.id] = resource

        ranked_ids = sorted(
            weighted_scores.keys(), key=lambda rid: weighted_scores[rid], reverse=True
        )
        ranked_resources = []
        for rid in ranked_ids:
            resource = resource_map[rid]
            resource.hybrid_score = round(weighted_scores[rid], 4)
            ranked_resources.append(resource)

        ranked_resources = deduplicate_resources(ranked_resources)
        return ranked_resources[: max(1, limit)]

    @classmethod
    def get_recommendations_for_dashboard(cls, user, limit: int = 5) -> dict:
        """Provide grouped strategy outputs for dashboard widgets."""
        return {
            "trending": cls.get_recommender("trending").recommend(user, limit=limit),
            "course_based": cls.get_recommender("course_based").recommend(
                user, limit=limit
            ),
            "behavior": cls.get_recommender("behavior").recommend(user, limit=limit),
            "hybrid": cls.get_hybrid_recommendations(user, limit=limit),
        }


__all__ = [
    "BaseRecommender",
    "TrendingRecommender",
    "CourseBasedRecommender",
    "BehaviorBasedRecommender",
    "RecommendationService",
]
