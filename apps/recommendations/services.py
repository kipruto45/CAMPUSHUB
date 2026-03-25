"""Recommendation services implementing hybrid ranking automations."""

from __future__ import annotations

import math
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.activity.models import ActivityType, RecentActivity
from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.ratings.models import Rating
from apps.recommendations.models import (RecommendationCache,
                                         UserInterestProfile)
from apps.resources.models import Resource

# Trending weights
TRENDING_DOWNLOAD_WEIGHT = 0.45
TRENDING_VIEW_WEIGHT = 0.20
TRENDING_BOOKMARK_WEIGHT = 0.15
TRENDING_FAVORITE_WEIGHT = 0.10
TRENDING_RATING_WEIGHT = 0.10

# Popularity-based recommendation weights (most viewed, downloaded, favorited)
POPULARITY_VIEW_WEIGHT = 0.25
POPULARITY_DOWNLOAD_WEIGHT = 0.45
POPULARITY_FAVORITE_WEIGHT = 0.30

# Optional: rating weight for improved formula
POPULARITY_RATING_WEIGHT = 0.10
POPULARITY_DOWNLOAD_MAX = 2.0
POPULARITY_RATING_MAX = 1.0
ACADEMIC_DOWNLOAD_BONUS_WEIGHT = 0.03
ACADEMIC_RATING_BONUS_WEIGHT = 0.20

# Recency multipliers
RECENCY_7_DAYS = 1.20
RECENCY_30_DAYS = 1.10
RECENCY_OLDER = 1.00

# Course match weights (per specification)
COURSE_FACULTY_WEIGHT = 1
COURSE_DEPARTMENT_WEIGHT = 2
COURSE_COURSE_WEIGHT = 4  # Highest - same course is strongest signal
COURSE_YEAR_WEIGHT = 2
COURSE_SEMESTER_WEIGHT = 1

# Related-resource weights
RELATED_UNIT_WEIGHT = 5
RELATED_COURSE_WEIGHT = 3
RELATED_TAG_WEIGHT = 2
RELATED_TYPE_WEIGHT = 1

# Final hybrid weights
HYBRID_COURSE_WEIGHT = 0.20
HYBRID_BEHAVIOR_WEIGHT = 0.25
HYBRID_RELATED_WEIGHT = 0.15
HYBRID_TRENDING_WEIGHT = 0.15
HYBRID_AI_WEIGHT = 0.25

# Content-based filtering weights
CONTENT_TAG_WEIGHT = 3.0
CONTENT_TITLE_WEIGHT = 2.0
CONTENT_DESCRIPTION_WEIGHT = 1.5
CONTENT_RESOURCE_TYPE_WEIGHT = 1.0
CONTENT_COURSE_WEIGHT = 2.5
CONTENT_UNIT_WEIGHT = 3.0

# Collaborative filtering weights
COLLAB_COURSE_WEIGHT = 3.0
COLLAB_YEAR_WEIGHT = 2.5
COLLAB_DEPARTMENT_WEIGHT = 2.0
COLLAB_FACULTY_WEIGHT = 1.5
COLLAB_SIMILARITY_THRESHOLD = 0.3

# Weights for the optional "hybrid of hybrids" endpoint.
META_HYBRID_POPULARITY_WEIGHT = 0.20
META_HYBRID_ACADEMIC_WEIGHT = 0.20
META_HYBRID_BEHAVIOR_WEIGHT = 0.20
META_HYBRID_CONTENT_WEIGHT = 0.20
META_HYBRID_COLLABORATIVE_WEIGHT = 0.20

# Time-based/Seasonal weights
SEASONAL_EXAM_PERIOD_WEIGHT = 2.0
SEASONAL_PROJECT_PERIOD_WEIGHT = 1.5
SEASONAL_REVISION_PERIOD_WEIGHT = 1.8
SEASONAL_BEGINNING_WEIGHT = 1.2
SEASONAL_DEFAULT_WEIGHT = 1.0

# Academic periods (months)
EXAM_PERIODS = [4, 5, 8, 12]  # April, May, August, December
PROJECT_PERIODS = [3, 9]  # March, September
REVISION_PERIODS = [1, 6, 11]  # January, June, November

# Lightweight semantic/embedding proxy weights.
AI_VIEW_WEIGHT = 1.0
AI_DOWNLOAD_WEIGHT = 3.0
AI_BOOKMARK_WEIGHT = 4.0
AI_FAVORITE_WEIGHT = 5.0
AI_MIN_RATING_WEIGHT = 4.0
AI_EMBEDDING_TOP_K = 120


def _approved_resource_queryset():
    return Resource.objects.filter(status="approved", is_public=True).select_related(
        "faculty",
        "department",
        "course",
        "unit",
        "uploaded_by",
    )


def _annotate_engagement(queryset):
    return queryset.annotate(
        # Avoid clashing with model fields (e.g. Resource.download_count).
        download_events_count=Count("downloads", distinct=True),
        bookmark_events_count=Count("bookmarks", distinct=True),
        favorite_events_count=Count(
            "favorites",
            filter=Q(favorites__favorite_type=FavoriteType.RESOURCE),
            distinct=True,
        ),
        rating_avg=Avg("ratings__value"),
    )


def _download_metric(resource: Resource) -> float:
    return float(
        getattr(resource, "download_events_count", None)
        or getattr(resource, "download_count", 0)
        or 0
    )


def _bookmark_metric(resource: Resource) -> float:
    return float(getattr(resource, "bookmark_events_count", None) or 0)


def _favorite_metric(resource: Resource) -> float:
    return float(getattr(resource, "favorite_events_count", None) or 0)


def _resource_tags(resource: Resource) -> set[str]:
    return {
        tag.strip().lower() for tag in (resource.tags or "").split(",") if tag.strip()
    }


def _tokenize_text(text: str) -> set[str]:
    """Extract meaningful tokens from text for content matching."""
    if not text:
        return set()
    # Remove common words and short tokens
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "from",
        "as",
        "into",
        "through",
    }
    tokens = set()
    for token in text.lower().split():
        cleaned = "".join(c for c in token if c.isalnum())
        if cleaned and len(cleaned) > 2 and cleaned not in stop_words:
            tokens.add(cleaned)
    return tokens


def _embed_tokens(tokens: set[str], size: int = 32) -> list[float]:
    """
    Lightweight deterministic embedding: hash tokens into a fixed-size vector.
    Avoids heavyweight ML deps while enabling semantic-ish similarity.
    """
    vec = [0.0] * size
    for token in tokens:
        h = abs(hash(token)) % size
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) or 0.0


def _resource_interest_tokens(resource: Resource) -> set[str]:
    """Build lexical token set representing a resource."""
    tokens = set(_resource_tags(resource))
    tokens.update(_tokenize_text(resource.title or ""))
    tokens.update(_tokenize_text(resource.description or ""))
    if resource.resource_type:
        tokens.add(resource.resource_type.lower())
    if getattr(resource, "course", None) and resource.course.name:
        tokens.update(_tokenize_text(resource.course.name))
    if getattr(resource, "unit", None) and resource.unit.name:
        tokens.update(_tokenize_text(resource.unit.name))
    return tokens


def semantic_similarity(resource: Resource, query_tokens: set[str]) -> float:
    """
    Compute cosine similarity between hashed embeddings of resource tokens and query tokens.
    """
    resource_vec = _embed_tokens(_resource_interest_tokens(resource))
    query_vec = _embed_tokens(query_tokens)
    return _cosine(resource_vec, query_vec)


def _behavior_summary_from_profile(profile: dict) -> dict:
    """Build compact, JSON-serializable user behavior summary."""
    return {
        "viewed_count": len(profile["viewed_resource_ids"]),
        "viewed_courses": sorted(str(cid) for cid in profile["viewed_courses"]),
        "viewed_units": sorted(str(uid) for uid in profile["viewed_units"]),
        "downloaded_tags": sorted(profile["downloaded_tags"]),
        "bookmarked_types": sorted(profile["bookmarked_types"]),
        "favorite_tags": sorted(profile["favorite_tags"]),
        "high_rated_resource_ids": sorted(
            str(rid) for rid in profile["high_rated_resource_ids"]
        ),
    }


def _collect_weighted_user_interest_terms(user) -> dict[str, float]:
    """Collect weighted term vector from user interactions."""
    term_weights: dict[str, float] = {}

    def _add_resource_terms(resource: Resource, weight: float):
        if not resource:
            return
        for token in _resource_interest_tokens(resource):
            term_weights[token] = term_weights.get(token, 0.0) + float(weight)

    views = RecentActivity.objects.filter(
        user=user,
        activity_type=ActivityType.VIEWED_RESOURCE,
        resource__isnull=False,
    ).select_related("resource")[:80]
    for activity in views:
        _add_resource_terms(activity.resource, AI_VIEW_WEIGHT)

    downloads = Download.objects.filter(
        user=user,
        resource__isnull=False,
        resource__status="approved",
    ).select_related("resource")[:80]
    for download in downloads:
        _add_resource_terms(download.resource, AI_DOWNLOAD_WEIGHT)

    bookmarks = Bookmark.objects.filter(
        user=user,
        resource__isnull=False,
    ).select_related("resource")[:80]
    for bookmark in bookmarks:
        _add_resource_terms(bookmark.resource, AI_BOOKMARK_WEIGHT)

    favorites = Favorite.objects.filter(
        user=user,
        favorite_type=FavoriteType.RESOURCE,
        resource__isnull=False,
    ).select_related("resource")[:80]
    for favorite in favorites:
        _add_resource_terms(favorite.resource, AI_FAVORITE_WEIGHT)

    ratings = Rating.objects.filter(
        user=user,
        value__gte=4,
        resource__isnull=False,
    ).select_related("resource")[:80]
    for rating in ratings:
        _add_resource_terms(
            rating.resource, max(float(rating.value), AI_MIN_RATING_WEIGHT)
        )

    return term_weights


def _cosine_similarity_sparse(
    user_vector: dict[str, float], resource_tokens: set[str]
) -> float:
    """Compute cosine similarity between sparse user vector and resource tokens."""
    if not user_vector or not resource_tokens:
        return 0.0
    dot = sum(float(user_vector.get(token, 0.0)) for token in resource_tokens)
    if dot <= 0:
        return 0.0
    user_norm = math.sqrt(sum(value * value for value in user_vector.values()))
    resource_norm = math.sqrt(len(resource_tokens))
    if user_norm == 0 or resource_norm == 0:
        return 0.0
    return min(max(dot / (user_norm * resource_norm), 0.0), 1.0)


def refresh_user_interest_profile(user):
    """Recompute and persist user interest profile from interactions."""
    if not user or not user.is_authenticated:
        return None

    behavior = get_user_behavior_profile(user)
    favorite_tags = sorted(behavior["downloaded_tags"] | behavior["favorite_tags"])
    favorite_units = sorted(str(unit_id) for unit_id in behavior["viewed_units"])
    favorite_types = sorted(behavior["bookmarked_types"])
    summary = _behavior_summary_from_profile(behavior)
    weighted_terms = _collect_weighted_user_interest_terms(user)
    top_embedding_terms = sorted(
        weighted_terms.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:AI_EMBEDDING_TOP_K]
    summary["embedding_terms"] = [
        {"t": token, "w": round(float(weight), 4)}
        for token, weight in top_embedding_terms
    ]
    summary["embedding_version"] = "semantic-v1"

    profile, _ = UserInterestProfile.objects.update_or_create(
        user=user,
        defaults={
            "favorite_tags": favorite_tags,
            "favorite_units": favorite_units,
            "favorite_resource_types": favorite_types,
            "behavior_summary": summary,
            "last_computed_at": timezone.now(),
        },
    )
    return profile


def _get_current_academic_period() -> str:
    """
    Determine current academic period based on month.

    Returns:
    - 'exam' for exam periods (April, May, August, December)
    - 'project' for project periods (March, September)
    - 'revision' for revision periods (January, June, November)
    - 'beginning' for semester beginning (February, July)
    - 'default' for regular periods
    """
    current_month = timezone.now().month

    if current_month in EXAM_PERIODS:
        return "exam"
    elif current_month in PROJECT_PERIODS:
        return "project"
    elif current_month in REVISION_PERIODS:
        return "revision"
    elif current_month in [2, 7]:  # February, July
        return "beginning"
    else:
        return "default"


def _get_seasonal_weight(resource: Resource) -> float:
    """
    Calculate seasonal weight based on resource metadata and current period.

    Boost resources that are relevant to the current academic period.
    """
    period = _get_current_academic_period()

    # Check resource tags/description for period-relevant keywords
    tags_lower = (resource.tags or "").lower()
    description_lower = (resource.description or "").lower()
    title_lower = resource.title.lower()

    content = " ".join([tags_lower, description_lower, title_lower])

    if period == "exam":
        # Boost exam-related content
        exam_keywords = [
            "exam",
            "past paper",
            "question",
            "test",
            "midterm",
            "final",
            "examination",
            "quiz",
            "assessment",
        ]
        if any(kw in content for kw in exam_keywords):
            return SEASONAL_EXAM_PERIOD_WEIGHT
    elif period == "project":
        # Boost project-related content
        project_keywords = [
            "project",
            "assignment",
            "practical",
            "lab",
            "report",
            "case study",
            "proposal",
            "thesis",
        ]
        if any(kw in content for kw in project_keywords):
            return SEASONAL_PROJECT_PERIOD_WEIGHT
    elif period == "revision":
        # Boost revision-related content
        revision_keywords = [
            "notes",
            "summary",
            "review",
            "cheat sheet",
            "quick",
            "key points",
            "important",
            "recap",
        ]
        if any(kw in content for kw in revision_keywords):
            return SEASONAL_REVISION_PERIOD_WEIGHT
    elif period == "beginning":
        # Boost introductory content
        beginning_keywords = [
            "introduction",
            " basics",
            "beginner",
            "getting started",
            "tutorial",
            "intro",
            "fundamentals",
        ]
        if any(kw in content for kw in beginning_keywords):
            return SEASONAL_BEGINNING_WEIGHT

    return SEASONAL_DEFAULT_WEIGHT


def _get_period_reason(period: str) -> str:
    """Get human-readable reason for current period."""
    period_reasons = {
        "exam": "Essential for exam preparation",
        "project": "Great for your project work",
        "revision": "Perfect for revision",
        "beginning": "Start the semester right",
        "default": "Recommended for you",
    }
    return period_reasons.get(period, "Recommended for you")


def get_seasonal_recommendations(limit: int = 10, exclude_ids: set | None = None):
    """
    Get time-based/seasonal recommendations based on academic calendar.

    This algorithm boosts resources relevant to the current academic period:
    - Exam periods (April, May, August, December): Exam papers, questions
    - Project periods (March, September): Projects, assignments
    - Revision periods (January, June, November): Notes, summaries
    - Beginning (February, July): Introductory materials
    """
    current_period = _get_current_academic_period()
    period_reason = _get_period_reason(current_period)

    # Get base resources (approved and public)
    queryset = _annotate_engagement(_approved_resource_queryset())

    if exclude_ids:
        queryset = queryset.exclude(id__in=exclude_ids)

    ranked = []
    for resource in queryset:
        # Calculate seasonal weight
        seasonal_weight = _get_seasonal_weight(resource)

        # Calculate base popularity score
        popularity = getattr(resource, "popularity_score", None)
        if popularity is None:
            popularity = calculate_popularity_score(resource)

        # Apply seasonal boost
        seasonal_score = popularity * seasonal_weight

        resource.seasonal_score = round(seasonal_score, 4)
        resource.recommendation_reason = period_reason
        ranked.append(resource)

    # Sort by seasonal score
    ranked.sort(
        key=lambda item: (item.seasonal_score, _download_metric(item)), reverse=True
    )
    return ranked[: max(1, limit)]


def invalidate_user_recommendation_cache(user, categories: list[str] | None = None):
    """Remove stale recommendation cache rows for a user."""
    if not user or not user.is_authenticated:
        return
    queryset = RecommendationCache.objects.filter(user=user)
    if categories:
        queryset = queryset.filter(category__in=categories)
    queryset.delete()


def invalidate_resource_recommendation_cache(resource: Resource):
    """Remove cached rows that point to a changed/deleted resource."""
    RecommendationCache.objects.filter(resource=resource).delete()


def _get_cached_recommendations(user, category: str, limit: int):
    """Fetch valid cached recommendations with score/reason hydrated."""
    now = timezone.now()
    rows = (
        RecommendationCache.objects.filter(
            user=user,
            category=category,
            expires_at__gt=now,
            resource__status="approved",
            resource__is_public=True,
        )
        .select_related("resource")
        .order_by("rank")[: max(1, limit)]
    )
    if not rows:
        return []

    cached = []
    for row in rows:
        resource = row.resource
        resource.final_score = row.score
        resource.recommendation_reason = row.reason or "Recommended for you"
        cached.append(resource)
    return cached


def _cache_recommendations(
    user, category: str, resources: list[Resource], *, ttl_hours: int = 24
):
    """Persist recommendation rows for faster dashboard/for-you reads."""
    if not user or not user.is_authenticated:
        return

    expires_at = timezone.now() + timedelta(hours=ttl_hours)
    RecommendationCache.objects.filter(user=user, category=category).delete()

    rows = []
    for rank, resource in enumerate(resources, start=1):
        score = float(
            getattr(resource, "final_score", None)
            or getattr(resource, "personal_score", None)
            or getattr(resource, "trending_score", None)
            or getattr(resource, "course_match_score", None)
            or getattr(resource, "related_score", None)
            or 0.0
        )
        rows.append(
            RecommendationCache(
                user=user,
                resource=resource,
                category=category,
                score=score,
                reason=getattr(resource, "recommendation_reason", "")[:255],
                rank=rank,
                expires_at=expires_at,
            )
        )
    if rows:
        RecommendationCache.objects.bulk_create(rows, batch_size=200)


def _extract_content_profile(resources: list[Resource]) -> dict:
    """
    Extract content profile from a list of resources the user interacted with.

    Returns a profile with:
    - tags: set of tags from interacted resources
    - title_tokens: set of meaningful title words
    - description_tokens: set of meaningful description words
    - resource_types: set of resource types
    - course_ids: set of course IDs
    - unit_ids: set of unit IDs
    """
    profile = {
        "tags": set(),
        "title_tokens": set(),
        "description_tokens": set(),
        "resource_types": set(),
        "course_ids": set(),
        "unit_ids": set(),
    }

    for resource in resources:
        # Add tags
        profile["tags"].update(_resource_tags(resource))

        # Add title tokens
        profile["title_tokens"].update(_tokenize_text(resource.title))

        # Add description tokens
        profile["description_tokens"].update(_tokenize_text(resource.description))

        # Add resource type
        if resource.resource_type:
            profile["resource_types"].add(resource.resource_type.lower())

        # Add course/unit
        if resource.course_id:
            profile["course_ids"].add(resource.course_id)
        if resource.unit_id:
            profile["unit_ids"].add(resource.unit_id)

    return profile


def calculate_content_similarity(resource: Resource, content_profile: dict) -> float:
    """
    Calculate content-based similarity score between a resource and user's content profile.

    Scoring:
    - Tags match: 3.0 points per matching tag
    - Title match: 2.0 points per matching token
    - Description match: 1.5 points per matching token
    - Resource type match: 1.0 points
    - Course match: 2.5 points
    - Unit match: 3.0 points

    Normalized to 0-1 range.
    """
    if not content_profile or not any(content_profile.values()):
        return 0.0

    score = 0.0
    max_score = 0.0

    # Tag similarity
    resource_tags = _resource_tags(resource)
    if resource_tags and content_profile["tags"]:
        tag_overlap = resource_tags & content_profile["tags"]
        score += len(tag_overlap) * CONTENT_TAG_WEIGHT
        max_score += max(len(content_profile["tags"]), 1) * CONTENT_TAG_WEIGHT

    # Title token similarity
    resource_title_tokens = _tokenize_text(resource.title)
    if resource_title_tokens and content_profile["title_tokens"]:
        title_overlap = resource_title_tokens & content_profile["title_tokens"]
        score += len(title_overlap) * CONTENT_TITLE_WEIGHT
        max_score += max(len(content_profile["title_tokens"]), 1) * CONTENT_TITLE_WEIGHT

    # Description token similarity
    resource_desc_tokens = _tokenize_text(resource.description)
    if resource_desc_tokens and content_profile["description_tokens"]:
        desc_overlap = resource_desc_tokens & content_profile["description_tokens"]
        score += len(desc_overlap) * CONTENT_DESCRIPTION_WEIGHT
        max_score += (
            max(len(content_profile["description_tokens"]), 1)
            * CONTENT_DESCRIPTION_WEIGHT
        )

    # Resource type match
    if (
        resource.resource_type
        and resource.resource_type.lower() in content_profile["resource_types"]
    ):
        score += CONTENT_RESOURCE_TYPE_WEIGHT
    max_score += CONTENT_RESOURCE_TYPE_WEIGHT

    # Course match
    if resource.course_id and resource.course_id in content_profile["course_ids"]:
        score += CONTENT_COURSE_WEIGHT
    max_score += CONTENT_COURSE_WEIGHT

    # Unit match (strongest signal)
    if resource.unit_id and resource.unit_id in content_profile["unit_ids"]:
        score += CONTENT_UNIT_WEIGHT
    max_score += CONTENT_UNIT_WEIGHT

    # Normalize to 0-1
    if max_score > 0:
        return min(score / max_score, 1.0)
    return 0.0


def get_user_content_profile(user) -> dict:
    """
    Build content profile from user's interaction history.

    Uses:
    - Downloaded resources
    - Viewed resources
    - Bookmarked resources
    - Favorited resources
    - Highly rated resources
    """
    if not user or not user.is_authenticated:
        return {}

    # Get resources from various interactions
    interacted_resources = []

    # Downloads
    downloads = Download.objects.filter(
        user=user, resource__isnull=False, resource__status="approved"
    ).select_related("resource")[:50]
    interacted_resources.extend([d.resource for d in downloads])

    # Views
    views = RecentActivity.objects.filter(
        user=user, activity_type=ActivityType.VIEWED_RESOURCE, resource__isnull=False
    ).select_related("resource")[:50]
    interacted_resources.extend([v.resource for v in views])

    # Bookmarks
    bookmarks = Bookmark.objects.filter(
        user=user, resource__isnull=False
    ).select_related("resource")[:50]
    interacted_resources.extend([b.resource for b in bookmarks])

    # Favorites
    favorites = Favorite.objects.filter(
        user=user, favorite_type=FavoriteType.RESOURCE, resource__isnull=False
    ).select_related("resource")[:50]
    interacted_resources.extend([f.resource for f in favorites])

    # High ratings
    high_ratings = Rating.objects.filter(
        user=user, value__gte=4, resource__isnull=False
    ).select_related("resource")[:50]
    interacted_resources.extend([r.resource for r in high_ratings])

    # Remove duplicates and extract profile
    unique_resources = list({r.id: r for r in interacted_resources if r}.values())
    return _extract_content_profile(unique_resources)


def get_content_based_recommendations(
    user, limit: int = 10, exclude_ids: set | None = None
):
    """
    Get content-based recommendations for a user.

    This algorithm recommends resources similar to ones the user has:
    - Downloaded
    - Viewed
    - Bookmarked
    - Favorited
    - Highly rated

    Based on:
    - Tags
    - Title
    - Description
    - Resource type
    - Course
    - Unit
    """
    if not user or not user.is_authenticated:
        return []

    # Build content profile from user's interactions
    content_profile = get_user_content_profile(user)
    if not content_profile or not any(content_profile.values()):
        return []

    # Get resources user has already interacted with
    consumed_ids = set()
    consumed_ids.update(
        Download.objects.filter(user=user).values_list("resource_id", flat=True)
    )
    consumed_ids.update(
        RecentActivity.objects.filter(
            user=user, activity_type=ActivityType.VIEWED_RESOURCE
        ).values_list("resource_id", flat=True)
    )
    consumed_ids.update(
        Bookmark.objects.filter(user=user).values_list("resource_id", flat=True)
    )
    consumed_ids.update(
        Favorite.objects.filter(
            user=user, favorite_type=FavoriteType.RESOURCE
        ).values_list("resource_id", flat=True)
    )

    if exclude_ids:
        consumed_ids.update(exclude_ids)

    # Get candidate resources
    queryset = _approved_resource_queryset().exclude(id__in=consumed_ids)
    if not queryset.exists():
        return []

    # Score each resource
    ranked = []
    for resource in queryset:
        content_score = calculate_content_similarity(resource, content_profile)
        if content_score > 0:
            resource.content_score = content_score
            resource.recommendation_reason = "Similar to resources you've viewed"
            ranked.append(resource)

    # Sort by content similarity score
    ranked.sort(
        key=lambda item: (item.content_score, _download_metric(item)), reverse=True
    )
    return ranked[: max(1, limit)]


def _get_user_academic_profile(user) -> dict:
    """
    Extract academic profile from user.

    Returns:
    - faculty_id
    - department_id
    - course_id
    - year_of_study
    - semester
    """
    profile = {
        "faculty_id": None,
        "department_id": None,
        "course_id": None,
        "year_of_study": None,
        "semester": None,
    }

    if not user:
        return profile

    # From user model
    if hasattr(user, "faculty_id") and user.faculty_id:
        profile["faculty_id"] = user.faculty_id
    if hasattr(user, "department_id") and user.department_id:
        profile["department_id"] = user.department_id
    if hasattr(user, "course_id") and user.course_id:
        profile["course_id"] = user.course_id
    if hasattr(user, "year_of_study") and user.year_of_study:
        profile["year_of_study"] = user.year_of_study

    # From profile
    if hasattr(user, "profile") and user.profile:
        p = user.profile
        if hasattr(p, "faculty_id") and p.faculty_id:
            profile["faculty_id"] = p.faculty_id
        if hasattr(p, "department_id") and p.department_id:
            profile["department_id"] = p.department_id
        if hasattr(p, "course_id") and p.course_id:
            profile["course_id"] = p.course_id
        if hasattr(p, "year_of_study") and p.year_of_study:
            profile["year_of_study"] = p.year_of_study

    return profile


def _calculate_user_similarity(profile1: dict, profile2: dict) -> float:
    """
    Calculate similarity between two users based on academic profile.

    Returns value between 0 and 1.
    """
    score = 0.0
    max_score = 0.0

    # Course match (highest)
    if profile1.get("course_id") and profile2.get("course_id"):
        if profile1["course_id"] == profile2["course_id"]:
            score += COLLAB_COURSE_WEIGHT
        max_score += COLLAB_COURSE_WEIGHT

    # Year match
    if profile1.get("year_of_study") and profile2.get("year_of_study"):
        if profile1["year_of_study"] == profile2["year_of_study"]:
            score += COLLAB_YEAR_WEIGHT
        max_score += COLLAB_YEAR_WEIGHT

    # Department match
    if profile1.get("department_id") and profile2.get("department_id"):
        if profile1["department_id"] == profile2["department_id"]:
            score += COLLAB_DEPARTMENT_WEIGHT
        max_score += COLLAB_DEPARTMENT_WEIGHT

    # Faculty match
    if profile1.get("faculty_id") and profile2.get("faculty_id"):
        if profile1["faculty_id"] == profile2["faculty_id"]:
            score += COLLAB_FACULTY_WEIGHT
        max_score += COLLAB_FACULTY_WEIGHT

    if max_score > 0:
        return score / max_score
    return 0.0


def get_collaborative_recommendations(
    user, limit: int = 10, exclude_ids: set | None = None
):
    """
    Get collaborative filtering recommendations.

    This algorithm recommends resources that similar students have downloaded or liked.
    Similarity is based on:
    - Same course (highest weight)
    - Same year of study
    - Same department
    - Same faculty

    Process:
    1. Get current user's academic profile
    2. Find similar users (same course/year)
    3. Get resources downloaded/favorited by similar users
    4. Rank by number of similar users who interacted + similarity score
    """
    if not user or not user.is_authenticated:
        return []

    # Get user's academic profile
    user_profile = _get_user_academic_profile(user)

    # Need at least course or year to find similar users
    if not user_profile.get("course_id") and not user_profile.get("year_of_study"):
        return []

    # Find similar users based on academic profile
    from apps.accounts.models import User

    # Build query for similar users
    similar_users_query = User.objects.filter(is_active=True).exclude(id=user.id)

    if user_profile.get("course_id"):
        similar_users_query = similar_users_query.filter(
            course_id=user_profile["course_id"]
        )
    elif user_profile.get("year_of_study"):
        similar_users_query = similar_users_query.filter(
            year_of_study=user_profile["year_of_study"]
        )

    similar_user_ids = list(similar_users_query.values_list("id", flat=True)[:200])

    if not similar_user_ids:
        return []

    # Get resources downloaded by similar users
    downloaded_by_similar = (
        Download.objects.filter(
            user_id__in=similar_user_ids,
            resource__status="approved",
            resource__is_public=True,
        )
        .values("resource_id", "user_id")
        .distinct()[:500]
    )

    # Get resources favorited by similar users
    favorited_by_similar = (
        Favorite.objects.filter(
            user_id__in=similar_user_ids,
            favorite_type=FavoriteType.RESOURCE,
            resource__status="approved",
            resource__is_public=True,
        )
        .values("resource_id", "user_id")
        .distinct()[:500]
    )

    # Count interactions per resource
    resource_interactions = {}

    for download in downloaded_by_similar:
        resource_id = download["resource_id"]
        if resource_id not in resource_interactions:
            resource_interactions[resource_id] = {"count": 0, "users": set()}
        resource_interactions[resource_id]["count"] += 1
        resource_interactions[resource_id]["users"].add(download["user_id"])

    for fav in favorited_by_similar:
        resource_id = fav["resource_id"]
        if resource_id not in resource_interactions:
            resource_interactions[resource_id] = {"count": 0, "users": set()}
        # Favorites count more than downloads
        resource_interactions[resource_id]["count"] += 2
        resource_interactions[resource_id]["users"].add(fav["user_id"])

    if not resource_interactions:
        return []

    # Get resources already interacted by current user
    consumed_ids = set()
    consumed_ids.update(
        Download.objects.filter(user=user).values_list("resource_id", flat=True)
    )
    consumed_ids.update(
        Favorite.objects.filter(
            user=user, favorite_type=FavoriteType.RESOURCE
        ).values_list("resource_id", flat=True)
    )

    if exclude_ids:
        consumed_ids.update(exclude_ids)

    # Get candidate resources
    candidate_ids = [
        rid for rid in resource_interactions.keys() if rid not in consumed_ids
    ]

    if not candidate_ids:
        return []

    # Get resource details and calculate scores
    queryset = _approved_resource_queryset().filter(id__in=candidate_ids)

    ranked = []
    for resource in queryset:
        interaction_data = resource_interactions.get(
            resource.id, {"count": 0, "users": set()}
        )
        interaction_count = interaction_data["count"]
        interacting_users = interaction_data["users"]

        # Calculate average similarity with users who interacted
        if interacting_users:
            total_similarity = 0.0
            for sim_user_id in interacting_users:
                try:
                    sim_user = User.objects.get(id=sim_user_id)
                    sim_profile = _get_user_academic_profile(sim_user)
                    similarity = _calculate_user_similarity(user_profile, sim_profile)
                    total_similarity += similarity
                except User.DoesNotExist:
                    continue

            avg_similarity = (
                total_similarity / len(interacting_users) if interacting_users else 0
            )
        else:
            avg_similarity = 0

        # Final score: interaction count * average similarity
        collab_score = interaction_count * avg_similarity

        if collab_score > 0:
            resource.collab_score = round(collab_score, 4)
            resource.recommendation_reason = "Popular among students in your course"
            ranked.append(resource)

    # Sort by collaborative score
    ranked.sort(
        key=lambda item: (item.collab_score, _download_metric(item)), reverse=True
    )
    return ranked[: max(1, limit)]


def get_hybrid_recommendations(user, limit: int = 10, exclude_ids: set | None = None):
    """
    Get hybrid recommendations combining all signals.

    This algorithm combines:
    - Popularity score (20% weight)
    - Academic match score (20% weight)
    - Behavior-based score (20% weight)
    - Content similarity score (20% weight)
    - Collaborative filtering score (20% weight)

    Each component is normalized to 0-1 range before combining.
    """
    if not user or not user.is_authenticated:
        return get_popular_recommendations(limit=limit, exclude_ids=exclude_ids)

    # Get resources from all recommendation sources
    popularity = get_popular_recommendations(limit=limit * 3, exclude_ids=exclude_ids)
    academic = get_course_based_recommendations(
        user, limit=limit * 3, exclude_ids=exclude_ids
    )
    behavior = get_personalized_recommendations(
        user, limit=limit * 3, exclude_ids=exclude_ids
    )
    content = get_content_based_recommendations(
        user, limit=limit * 3, exclude_ids=exclude_ids
    )
    collab = get_collaborative_recommendations(
        user, limit=limit * 3, exclude_ids=exclude_ids
    )

    # Collect all candidate resource IDs
    all_candidates = {}

    for resource in popularity:
        all_candidates[resource.id] = {
            "resource": resource,
            "popularity_score": getattr(resource, "popularity_score", 0) or 0,
            "academic_score": 0,
            "behavior_score": 0,
            "content_score": 0,
            "collab_score": 0,
        }

    for resource in academic:
        if resource.id not in all_candidates:
            all_candidates[resource.id] = {
                "resource": resource,
                "popularity_score": 0,
                "academic_score": 0,
                "behavior_score": 0,
                "content_score": 0,
                "collab_score": 0,
            }
        all_candidates[resource.id]["academic_score"] = (
            getattr(resource, "course_match_score", 0) or 0
        )

    for resource in behavior:
        if resource.id not in all_candidates:
            all_candidates[resource.id] = {
                "resource": resource,
                "popularity_score": 0,
                "academic_score": 0,
                "behavior_score": 0,
                "content_score": 0,
                "collab_score": 0,
            }
        all_candidates[resource.id]["behavior_score"] = (
            getattr(resource, "personal_score", 0) or 0
        )

    for resource in content:
        if resource.id not in all_candidates:
            all_candidates[resource.id] = {
                "resource": resource,
                "popularity_score": 0,
                "academic_score": 0,
                "behavior_score": 0,
                "content_score": 0,
                "collab_score": 0,
            }
        all_candidates[resource.id]["content_score"] = (
            getattr(resource, "content_score", 0) or 0
        )

    for resource in collab:
        if resource.id not in all_candidates:
            all_candidates[resource.id] = {
                "resource": resource,
                "popularity_score": 0,
                "academic_score": 0,
                "behavior_score": 0,
                "content_score": 0,
                "collab_score": 0,
            }
        all_candidates[resource.id]["collab_score"] = (
            getattr(resource, "collab_score", 0) or 0
        )

    # Find max values for normalization
    max_popularity = (
        max((c["popularity_score"] for c in all_candidates.values()), default=1) or 1
    )
    max_academic = (
        max((c["academic_score"] for c in all_candidates.values()), default=1) or 1
    )
    max_behavior = (
        max((c["behavior_score"] for c in all_candidates.values()), default=1) or 1
    )
    max_content = (
        max((c["content_score"] for c in all_candidates.values()), default=1) or 1
    )
    max_collab = (
        max((c["collab_score"] for c in all_candidates.values()), default=1) or 1
    )

    # Calculate hybrid scores
    ranked = []
    for resource_id, scores in all_candidates.items():
        resource = scores["resource"]

        # Normalize scores to 0-1 range
        norm_popularity = scores["popularity_score"] / max_popularity
        norm_academic = (
            min(scores["academic_score"] / max_academic, 1.0) if max_academic > 0 else 0
        )
        norm_behavior = (
            min(scores["behavior_score"] / max_behavior, 1.0) if max_behavior > 0 else 0
        )
        norm_content = (
            min(scores["content_score"] / max_content, 1.0) if max_content > 0 else 0
        )
        norm_collab = (
            min(scores["collab_score"] / max_collab, 1.0) if max_collab > 0 else 0
        )

        # Calculate weighted hybrid score
        hybrid_score = (
            (norm_popularity * META_HYBRID_POPULARITY_WEIGHT)
            + (norm_academic * META_HYBRID_ACADEMIC_WEIGHT)
            + (norm_behavior * META_HYBRID_BEHAVIOR_WEIGHT)
            + (norm_content * META_HYBRID_CONTENT_WEIGHT)
            + (norm_collab * META_HYBRID_COLLABORATIVE_WEIGHT)
        )

        resource.hybrid_score = round(hybrid_score, 4)

        # Determine best reason based on which score contributed most
        scores_dict = {
            "popularity": norm_popularity,
            "academic": norm_academic,
            "behavior": norm_behavior,
            "content": norm_content,
            "collab": norm_collab,
        }
        max_signal = max(scores_dict.items(), key=lambda x: x[1])

        if max_signal[1] > 0:
            if max_signal[0] == "academic":
                resource.recommendation_reason = _course_reason(resource, user)
            elif max_signal[0] == "popularity":
                resource.recommendation_reason = get_popularity_reason(resource)
            elif max_signal[0] == "behavior":
                resource.recommendation_reason = "Based on your recent activity"
            elif max_signal[0] == "content":
                resource.recommendation_reason = "Similar to resources you've viewed"
            elif max_signal[0] == "collab":
                resource.recommendation_reason = "Popular among students in your course"
        else:
            resource.recommendation_reason = "Recommended for you"

        ranked.append(resource)

    # Sort by hybrid score
    ranked.sort(
        key=lambda item: (item.hybrid_score, _download_metric(item)), reverse=True
    )
    return ranked[: max(1, limit)]


def _recency_multiplier(resource: Resource) -> float:
    age_days = max((timezone.now() - resource.created_at).days, 0)
    if age_days <= 7:
        return RECENCY_7_DAYS
    if age_days <= 30:
        return RECENCY_30_DAYS
    return RECENCY_OLDER


def calculate_trending_score(resource: Resource) -> float:
    """Weighted popularity score with recency boost."""
    downloads = _download_metric(resource)
    views = float(getattr(resource, "view_count", 0) or 0)
    bookmarks = _bookmark_metric(resource)
    favorites = _favorite_metric(resource)
    rating = float(getattr(resource, "rating_avg", 0) or 0)

    score = (
        (downloads * TRENDING_DOWNLOAD_WEIGHT)
        + (views * TRENDING_VIEW_WEIGHT)
        + (bookmarks * TRENDING_BOOKMARK_WEIGHT)
        + (favorites * TRENDING_FAVORITE_WEIGHT)
        + (rating * TRENDING_RATING_WEIGHT)
    )
    return round(score * _recency_multiplier(resource), 4)


def get_popularity_reason(resource: Resource) -> str:
    """
    Generate human-readable reason based on strongest engagement signal.

    Returns:
    - "Most downloaded by students" - if downloads are strongest
    - "Highly favorited by students" - if favorites are strongest
    - "Frequently viewed by students" - if views are strongest
    - "Trending this week" - if recency boost applies
    - "Popular resource on the platform" - default
    """
    downloads = _download_metric(resource)
    views = getattr(resource, "view_count", 0) or 0
    favorites = _favorite_metric(resource)

    # Find strongest signal
    if downloads >= views and downloads >= favorites:
        return "Most downloaded by students"
    elif favorites >= views:
        return "Highly favorited by students"
    elif views > 0:
        return "Frequently viewed by students"

    # Check recency
    age_days = (timezone.now() - resource.created_at).days
    if age_days <= 7:
        return "Trending this week"

    return "Popular resource on the platform"


def calculate_popularity_score(resource: Resource) -> float:
    """
    Calculate popularity-based recommendation score.

    Formula:
    base_score = (
        (view_count * 0.25) +
        (download_count * 0.45) +
        (favorite_count * 0.30)
    )

    With optional rating:
    base_score = (
        (view_count * 0.20) +
        (download_count * 0.45) +
        (favorite_count * 0.25) +
        (average_rating * 0.10)
    )

    Recency multiplier:
    - 7 days: 1.20
    - 30 days: 1.10
    - otherwise: 1.00

    final_score = base_score * recency_multiplier
    """
    downloads = _download_metric(resource)
    views = float(getattr(resource, "view_count", 0) or 0)
    favorites = _favorite_metric(resource)
    rating = float(getattr(resource, "rating_avg", 0) or 0)

    # Base score with optional rating
    if rating > 0:
        base_score = (
            (views * POPULARITY_VIEW_WEIGHT)
            + (downloads * POPULARITY_DOWNLOAD_WEIGHT)
            + (favorites * POPULARITY_FAVORITE_WEIGHT)
            + (rating * POPULARITY_RATING_WEIGHT)
        )
    else:
        # Without rating - normalize weights
        total_weight = (
            POPULARITY_VIEW_WEIGHT
            + POPULARITY_DOWNLOAD_WEIGHT
            + POPULARITY_FAVORITE_WEIGHT
        )
        base_score = (
            (views * (POPULARITY_VIEW_WEIGHT / total_weight))
            + (downloads * (POPULARITY_DOWNLOAD_WEIGHT / total_weight))
            + (favorites * (POPULARITY_FAVORITE_WEIGHT / total_weight))
        )

    # Apply recency multiplier
    age_days = (timezone.now() - resource.created_at).days
    if age_days <= 7:
        recency_multiplier = RECENCY_7_DAYS
    elif age_days <= 30:
        recency_multiplier = RECENCY_30_DAYS
    else:
        recency_multiplier = RECENCY_OLDER

    return round(base_score * recency_multiplier, 4)


def get_trending_resources(limit: int = 10, exclude_ids: set | None = None):
    """Return platform-wide trending resources."""
    queryset = _annotate_engagement(_approved_resource_queryset())
    if exclude_ids:
        queryset = queryset.exclude(id__in=exclude_ids)

    ranked = []
    for resource in queryset:
        resource.trending_score = calculate_trending_score(resource)
        ranked.append(resource)

    ranked.sort(
        key=lambda item: (item.trending_score, _download_metric(item), item.view_count),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def get_popular_recommendations(limit: int = 10, exclude_ids: set | None = None):
    """
    Get popular recommendations based on views, downloads, and favorites.

    This is the main popularity-based recommendation algorithm:
    - View count (0.25 weight)
    - Download count (0.45 weight)
    - Favorite count (0.30 weight)
    - Optional rating (0.10 weight)
    - Recency multiplier (1.20 for 7 days, 1.10 for 30 days)

    Returns resources sorted by popularity score descending.
    """
    queryset = _annotate_engagement(_approved_resource_queryset())
    if exclude_ids:
        queryset = queryset.exclude(id__in=exclude_ids)

    ranked = []
    for resource in queryset:
        resource.popularity_score = calculate_popularity_score(resource)
        resource.recommendation_reason = get_popularity_reason(resource)
        ranked.append(resource)

    # Sort by popularity score, then by downloads, then by views
    ranked.sort(
        key=lambda item: (
            item.popularity_score,
            _download_metric(item),
            item.view_count,
        ),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def calculate_course_match_score(resource: Resource, user) -> int:
    """
    Academic metadata match score with popularity bonus.

    Detects user's faculty, department, course, year, semester from:
    1. User model directly (if fields exist)
    2. User.profile (if profile exists)

    Scoring (per specification):
    - Same faculty: +1 point
    - Same department: +2 points
    - Same course: +5 points (highest)
    - Same year: +3 points
    - Same semester: +1 point

    Plus popularity bonus:
    - min(download_count * 0.03, 2) + min((average_rating or 0) * 0.2, 1)
    """
    if not user:
        return 0

    # Detect user's academic profile
    user_faculty_id = None
    user_department_id = None
    user_course_id = None
    user_year = None
    user_semester = None

    # Try to get from user model directly
    if hasattr(user, "faculty_id"):
        user_faculty_id = user.faculty_id
    if hasattr(user, "department_id"):
        user_department_id = user.department_id
    if hasattr(user, "course_id"):
        user_course_id = user.course_id
    if hasattr(user, "year_of_study"):
        user_year = user.year_of_study

    # Try to get from user.profile
    if hasattr(user, "profile") and user.profile:
        profile = user.profile
        if hasattr(profile, "faculty_id") and profile.faculty_id:
            user_faculty_id = profile.faculty_id
        if hasattr(profile, "department_id") and profile.department_id:
            user_department_id = profile.department_id
        if hasattr(profile, "course_id") and profile.course_id:
            user_course_id = profile.course_id
            # Get semester from course
            if hasattr(profile, "course") and profile.course:
                if hasattr(profile.course, "semester"):
                    user_semester = profile.course.semester
        if hasattr(profile, "year_of_study") and profile.year_of_study:
            user_year = profile.year_of_study

    academic_score = 0

    # Faculty match (+1)
    if user_faculty_id and hasattr(resource, "faculty_id") and resource.faculty_id:
        if user_faculty_id == resource.faculty_id:
            academic_score += COURSE_FACULTY_WEIGHT

    # Department match (+2)
    if (
        user_department_id
        and hasattr(resource, "department_id")
        and resource.department_id
    ):
        if user_department_id == resource.department_id:
            academic_score += COURSE_DEPARTMENT_WEIGHT

    # Course match (+5 - highest)
    if user_course_id and hasattr(resource, "course_id") and resource.course_id:
        if user_course_id == resource.course_id:
            academic_score += COURSE_COURSE_WEIGHT

    # Year match (+3)
    if user_year and hasattr(resource, "year_of_study") and resource.year_of_study:
        if user_year == resource.year_of_study:
            academic_score += COURSE_YEAR_WEIGHT

    # Semester match (+1)
    if user_semester and hasattr(resource, "semester") and resource.semester:
        if str(user_semester) == str(resource.semester):
            academic_score += COURSE_SEMESTER_WEIGHT

    # Add popularity bonus
    download_count = _download_metric(resource)
    average_rating = float(getattr(resource, "rating_avg", 0) or 0)

    popularity_bonus = min(
        download_count * ACADEMIC_DOWNLOAD_BONUS_WEIGHT, POPULARITY_DOWNLOAD_MAX
    ) + min(average_rating * ACADEMIC_RATING_BONUS_WEIGHT, POPULARITY_RATING_MAX)

    final_score = academic_score + popularity_bonus
    return round(final_score, 2)


def get_course_based_recommendations(
    user, limit: int = 10, exclude_ids: set | None = None
):
    """Recommend by faculty/department/course/year/semester alignment."""
    if not user or not user.is_authenticated:
        return get_trending_resources(limit=limit, exclude_ids=exclude_ids)

    consumed_ids = set()
    consumed_ids.update(
        Download.objects.filter(user=user, resource__isnull=False).values_list(
            "resource_id", flat=True
        )
    )
    if exclude_ids:
        consumed_ids.update(exclude_ids)

    queryset = _annotate_engagement(_approved_resource_queryset()).exclude(
        id__in=consumed_ids
    )
    ranked = []
    for resource in queryset:
        resource.course_match_score = calculate_course_match_score(resource, user)
        resource.recommendation_reason = _course_reason(resource, user)
        ranked.append(resource)

    ranked.sort(
        key=lambda item: (
            item.course_match_score,
            _download_metric(item),
            item.view_count,
            item.created_at,
        ),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def calculate_related_score(
    target_resource: Resource, candidate_resource: Resource
) -> int:
    """Rank similarity with unit/course/tags/type signals."""
    score = 0
    if (
        target_resource.unit_id
        and target_resource.unit_id == candidate_resource.unit_id
    ):
        score += RELATED_UNIT_WEIGHT
    if (
        target_resource.course_id
        and target_resource.course_id == candidate_resource.course_id
    ):
        score += RELATED_COURSE_WEIGHT

    overlap = _resource_tags(target_resource) & _resource_tags(candidate_resource)
    if overlap:
        score += RELATED_TAG_WEIGHT * len(overlap)

    if (
        target_resource.resource_type
        and target_resource.resource_type == candidate_resource.resource_type
    ):
        score += RELATED_TYPE_WEIGHT
    return score


def get_related_resources(
    resource: Resource, user=None, limit: int = 6, exclude_ids: set | None = None
):
    """Get resources related to the current resource."""
    queryset = _annotate_engagement(_approved_resource_queryset()).exclude(
        id=resource.id
    )
    if exclude_ids:
        queryset = queryset.exclude(id__in=exclude_ids)

    ranked = []
    for candidate in queryset:
        candidate.related_score = calculate_related_score(resource, candidate)
        if candidate.related_score > 0:
            candidate.recommendation_reason = f"Related to {resource.title}"
            ranked.append(candidate)

    ranked.sort(
        key=lambda item: (item.related_score, _download_metric(item), item.created_at),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def get_user_behavior_profile(user) -> dict:
    """Build user interest profile from interactions."""
    profile = {
        "viewed_resource_ids": set(),
        "viewed_courses": set(),
        "viewed_units": set(),
        "downloaded_tags": set(),
        "bookmarked_types": set(),
        "favorite_tags": set(),
        "high_rated_resource_ids": set(),
    }
    if not user or not user.is_authenticated:
        return profile

    view_activities = RecentActivity.objects.filter(
        user=user,
        activity_type=ActivityType.VIEWED_RESOURCE,
        resource__isnull=False,
    ).select_related("resource")[:100]
    for activity in view_activities:
        profile["viewed_resource_ids"].add(activity.resource_id)
        if activity.resource.course_id:
            profile["viewed_courses"].add(activity.resource.course_id)
        if activity.resource.unit_id:
            profile["viewed_units"].add(activity.resource.unit_id)

    downloads = Download.objects.filter(
        user=user, resource__isnull=False
    ).select_related("resource")[:100]
    for download in downloads:
        profile["viewed_resource_ids"].add(download.resource_id)
        profile["downloaded_tags"].update(_resource_tags(download.resource))
        if download.resource.resource_type:
            profile["bookmarked_types"].add(download.resource.resource_type)

    bookmarks = Bookmark.objects.filter(user=user).select_related("resource")[:100]
    for bookmark in bookmarks:
        profile["viewed_resource_ids"].add(bookmark.resource_id)
        profile["favorite_tags"].update(_resource_tags(bookmark.resource))
        if bookmark.resource.resource_type:
            profile["bookmarked_types"].add(bookmark.resource.resource_type)

    favorites = Favorite.objects.filter(
        user=user,
        favorite_type=FavoriteType.RESOURCE,
        resource__isnull=False,
    ).select_related("resource")[:100]
    for favorite in favorites:
        profile["viewed_resource_ids"].add(favorite.resource_id)
        profile["favorite_tags"].update(_resource_tags(favorite.resource))

    ratings = Rating.objects.filter(user=user, value__gte=4).values_list(
        "resource_id", flat=True
    )[:100]
    profile["high_rated_resource_ids"].update(ratings)
    profile["viewed_resource_ids"].update(ratings)
    return profile


def calculate_behavior_score(resource: Resource, behavior_profile: dict) -> float:
    """Compute behavior-based match score in [0, 1.2] range."""
    viewed_similarity = (
        1.0 if resource.course_id in behavior_profile["viewed_courses"] else 0.0
    )
    if resource.unit_id and resource.unit_id in behavior_profile["viewed_units"]:
        viewed_similarity = max(viewed_similarity, 1.0)

    resource_tags = _resource_tags(resource)
    download_similarity = (
        1.0 if resource_tags & behavior_profile["downloaded_tags"] else 0.0
    )
    bookmark_similarity = (
        1.0 if resource.resource_type in behavior_profile["bookmarked_types"] else 0.0
    )
    favorite_similarity = (
        1.0 if resource_tags & behavior_profile["favorite_tags"] else 0.0
    )
    rating_similarity = (
        1.0 if resource.id in behavior_profile["high_rated_resource_ids"] else 0.0
    )

    return (
        (viewed_similarity * 0.20)
        + (download_similarity * 0.30)
        + (bookmark_similarity * 0.20)
        + (favorite_similarity * 0.15)
        + (rating_similarity * 0.15)
    )


def _ai_similarity_proxy(
    resource: Resource, behavior_profile: dict, user=None
) -> float:
    """Lightweight semantic similarity using persisted sparse embeddings."""
    user_vector: dict[str, float] = {}
    interest_tokens = set(behavior_profile["downloaded_tags"]) | set(
        behavior_profile["favorite_tags"]
    )
    interest_tokens.update(
        str(value).lower() for value in behavior_profile["bookmarked_types"]
    )

    if user and getattr(user, "is_authenticated", False):
        profile = UserInterestProfile.objects.filter(user=user).first()
        if profile:
            summary = profile.behavior_summary or {}
            embedding_terms = summary.get("embedding_terms") or []
            if isinstance(embedding_terms, list):
                for item in embedding_terms:
                    if not isinstance(item, dict):
                        continue
                    token = str(item.get("t") or "").strip().lower()
                    weight = float(item.get("w") or 0.0)
                    if token and weight > 0:
                        user_vector[token] = user_vector.get(token, 0.0) + weight
            interest_tokens.update(
                str(tag).lower() for tag in (profile.favorite_tags or [])
            )
            interest_tokens.update(
                str(item).lower() for item in (profile.favorite_resource_types or [])
            )

    if not user_vector and user and getattr(user, "is_authenticated", False):
        user_vector = _collect_weighted_user_interest_terms(user)

    resource_tokens = _resource_interest_tokens(resource)
    semantic_similarity = _cosine_similarity_sparse(user_vector, resource_tokens)
    if semantic_similarity > 0:
        return semantic_similarity

    # Fallback to set overlap when there is not enough vector signal yet.
    if not interest_tokens:
        return 0.0
    overlap = resource_tokens & interest_tokens
    if not overlap:
        return 0.0
    union = resource_tokens | interest_tokens
    return min(len(overlap) / max(len(union), 1), 1.0)


def get_personalized_recommendations(
    user, limit: int = 10, exclude_ids: set | None = None
):
    """Behavior + popularity recommendations."""
    if not user or not user.is_authenticated:
        return get_trending_resources(limit=limit, exclude_ids=exclude_ids)

    behavior = get_user_behavior_profile(user)
    if not any(
        [
            behavior["viewed_courses"],
            behavior["viewed_units"],
            behavior["downloaded_tags"],
            behavior["bookmarked_types"],
            behavior["favorite_tags"],
            behavior["high_rated_resource_ids"],
        ]
    ):
        return get_course_based_recommendations(
            user, limit=limit, exclude_ids=exclude_ids
        )

    consumed_ids = set(behavior["viewed_resource_ids"])
    if exclude_ids:
        consumed_ids.update(exclude_ids)

    queryset = _annotate_engagement(_approved_resource_queryset()).exclude(
        id__in=consumed_ids
    )
    ranked = []
    for candidate in queryset:
        behavior_score = calculate_behavior_score(candidate, behavior)
        popularity_score = min(
            (_download_metric(candidate) + (candidate.view_count or 0)) / 300.0, 1.0
        )
        candidate.behavior_score = behavior_score
        candidate.personal_score = (behavior_score * 0.70) + (popularity_score * 0.30)
        candidate.recommendation_reason = "Based on your recent activity"
        ranked.append(candidate)

    ranked.sort(
        key=lambda item: (item.personal_score, _download_metric(item), item.created_at),
        reverse=True,
    )
    return ranked[: max(1, limit)]


def get_for_you_recommendations(user, limit: int = 10):
    """Hybrid final ranking."""
    if not user or not user.is_authenticated:
        return get_trending_resources(limit=limit)

    cached = _get_cached_recommendations(
        user, RecommendationCache.CATEGORY_FOR_YOU, limit
    )
    if len(cached) >= max(1, limit):
        return cached[: max(1, limit)]

    behavior = get_user_behavior_profile(user)
    refresh_user_interest_profile(user)
    trending = get_trending_resources(limit=limit * 3)
    course_based = get_course_based_recommendations(user, limit=limit * 3)
    behavior_based = get_personalized_recommendations(user, limit=limit * 3)

    candidate_ids = {
        resource.id for resource in [*trending, *course_based, *behavior_based]
    }
    if not candidate_ids:
        return []

    related_source_ids = list(behavior["viewed_resource_ids"])[:5]
    related_sources = list(
        Resource.objects.filter(
            id__in=related_source_ids,
            status="approved",
            is_public=True,
        )
    )

    queryset = _annotate_engagement(
        _approved_resource_queryset().filter(id__in=candidate_ids)
    )
    max_trending = (
        max([getattr(item, "trending_score", 0.0) for item in trending], default=1.0)
        or 1.0
    )
    ranked = []

    for resource in queryset:
        course_score = min(calculate_course_match_score(resource, user) / 10.0, 1.0)
        behavior_score = min(calculate_behavior_score(resource, behavior), 1.0)
        trending_score = min(calculate_trending_score(resource) / max_trending, 1.0)
        ai_similarity = _ai_similarity_proxy(resource, behavior, user=user)
        related_raw = 0
        for source in related_sources:
            if source.id == resource.id:
                continue
            related_raw = max(related_raw, calculate_related_score(source, resource))
        related_score = min(related_raw / 10.0, 1.0)

        final_score = (
            (course_score * HYBRID_COURSE_WEIGHT)
            + (behavior_score * HYBRID_BEHAVIOR_WEIGHT)
            + (related_score * HYBRID_RELATED_WEIGHT)
            + (trending_score * HYBRID_TRENDING_WEIGHT)
            + (ai_similarity * HYBRID_AI_WEIGHT)
        )
        resource.final_score = final_score
        resource.related_score = related_raw
        resource.recommendation_reason = _build_hybrid_reason(
            resource,
            user,
            behavior_score,
            course_score,
            trending_score,
            related_score,
        )
        ranked.append(resource)

    ranked.sort(
        key=lambda item: (item.final_score, _download_metric(item), item.created_at),
        reverse=True,
    )
    result = ranked[: max(1, limit)]
    _cache_recommendations(
        user, RecommendationCache.CATEGORY_FOR_YOU, result, ttl_hours=24
    )
    return result


def get_saved_based_recommendations(user, limit: int = 10):
    """Recommendations seeded by bookmarks/favorites."""
    if not user or not user.is_authenticated:
        return []

    cached = _get_cached_recommendations(
        user, RecommendationCache.CATEGORY_SAVED, limit
    )
    if len(cached) >= max(1, limit):
        return cached[: max(1, limit)]

    bookmarked_ids = list(
        Bookmark.objects.filter(user=user).values_list("resource_id", flat=True)[:10]
    )
    favorite_ids = list(
        Favorite.objects.filter(
            user=user, favorite_type=FavoriteType.RESOURCE
        ).values_list("resource_id", flat=True)[:10]
    )
    source_ids = set(bookmarked_ids + favorite_ids)
    if not source_ids:
        return []

    related_pool = []
    for source in Resource.objects.filter(id__in=source_ids, status="approved"):
        related_pool.extend(
            get_related_resources(source, user=user, limit=4, exclude_ids=source_ids)
        )

    dedup = {}
    for item in related_pool:
        existing = dedup.get(item.id)
        if not existing or getattr(item, "related_score", 0) > getattr(
            existing, "related_score", 0
        ):
            dedup[item.id] = item

    ranked = sorted(
        dedup.values(),
        key=lambda item: (
            getattr(item, "related_score", 0),
            _download_metric(item),
            item.created_at,
        ),
        reverse=True,
    )
    result = ranked[: max(1, limit)]
    _cache_recommendations(
        user, RecommendationCache.CATEGORY_SAVED, result, ttl_hours=24
    )
    return result


def get_download_based_recommendations(user, limit: int = 10):
    """Recommend resources similar to user's recent download history."""
    if not user or not user.is_authenticated:
        return []

    recent_downloads = Download.objects.filter(
        user=user,
        resource__status="approved",
        resource__is_public=True,
        resource__isnull=False,
    ).select_related("resource", "resource__course", "resource__unit")[:30]

    source_resources = [
        download.resource for download in recent_downloads if download.resource
    ]
    if not source_resources:
        return []

    consumed_ids = {resource.id for resource in source_resources}
    source_tags = set()
    source_types = set()
    source_course_ids = set()
    source_unit_ids = set()
    for resource in source_resources:
        source_tags.update(_resource_tags(resource))
        if resource.resource_type:
            source_types.add(resource.resource_type)
        if resource.course_id:
            source_course_ids.add(resource.course_id)
        if resource.unit_id:
            source_unit_ids.add(resource.unit_id)

    queryset = _annotate_engagement(
        _approved_resource_queryset().exclude(id__in=consumed_ids)
    )

    ranked = []
    for candidate in queryset:
        tag_overlap = len(_resource_tags(candidate) & source_tags)
        score = (
            (4 if candidate.unit_id in source_unit_ids else 0)
            + (2 if candidate.course_id in source_course_ids else 0)
            + (1 if candidate.resource_type in source_types else 0)
            + (tag_overlap * 2)
            + min(_download_metric(candidate) / 50.0, 1.0)
        )
        if score <= 0:
            continue
        candidate.personal_score = round(float(score), 4)
        candidate.recommendation_reason = "Based on your recent downloads"
        ranked.append(candidate)

    ranked.sort(
        key=lambda item: (
            getattr(item, "personal_score", 0),
            _download_metric(item),
            item.created_at,
        ),
        reverse=True,
    )
    result = ranked[: max(1, limit)]
    _cache_recommendations(
        user, RecommendationCache.CATEGORY_DOWNLOAD, result, ttl_hours=24
    )
    return result


def get_recommendation_reason(resource: Resource, user) -> str:
    """Human-readable explanation for recommendation cards."""
    explicit_reason = getattr(resource, "recommendation_reason", "")
    if explicit_reason:
        return explicit_reason

    # Use the course reason logic
    if user and getattr(user, "is_authenticated", False):
        reason = _course_reason(resource, user)
        if reason and reason != "Recommended for you":
            return reason

    # Fallback to popularity-based reasons
    if _download_metric(resource) >= 10:
        return "Popular with students recently"
    if getattr(resource, "average_rating", 0) and float(resource.average_rating) >= 4.0:
        return "Highly rated by learners"
    return "Recommended for you"


def _course_reason(resource: Resource, user) -> str:
    """
    Generate human-readable reason based on what matched.
    Per specification:
    - "Matches your course and year" - if same course and year
    - "Matches your course" - if same course only
    - "Popular in your department" - if same department
    - "Popular in your faculty" - if same faculty
    - "Recommended for you" - default

    Detects user's academic profile from User or UserProfile.
    """
    if not user:
        return "Recommended for you"

    # Get user academic info from user model or profile
    user_course_id = None
    user_department_id = None
    user_faculty_id = None
    user_year = None

    # From user model
    if hasattr(user, "course_id"):
        user_course_id = user.course_id
    if hasattr(user, "department_id"):
        user_department_id = user.department_id
    if hasattr(user, "faculty_id"):
        user_faculty_id = user.faculty_id
    if hasattr(user, "year_of_study"):
        user_year = user.year_of_study

    # From profile (override if exists)
    if hasattr(user, "profile") and user.profile:
        profile = user.profile
        if hasattr(profile, "course_id") and profile.course_id:
            user_course_id = profile.course_id
        if hasattr(profile, "department_id") and profile.department_id:
            user_department_id = profile.department_id
        if hasattr(profile, "faculty_id") and profile.faculty_id:
            user_faculty_id = profile.faculty_id
        if hasattr(profile, "year_of_study") and profile.year_of_study:
            user_year = profile.year_of_study

    # Check course and year match first (highest priority)
    if (
        user_course_id
        and hasattr(resource, "course_id")
        and resource.course_id == user_course_id
    ):
        if (
            user_year
            and hasattr(resource, "year_of_study")
            and resource.year_of_study == user_year
        ):
            return "Matches your course and year"
        return "Matches your course"

    # Check department match
    if (
        user_department_id
        and hasattr(resource, "department_id")
        and resource.department_id == user_department_id
    ):
        return "Popular in your department"

    # Check faculty match
    if (
        user_faculty_id
        and hasattr(resource, "faculty_id")
        and resource.faculty_id == user_faculty_id
    ):
        return "Popular in your faculty"

    return "Recommended for you"


def _build_hybrid_reason(
    resource: Resource,
    user,
    behavior_score: float,
    course_score: float,
    trending_score: float,
    related_score: float = 0.0,
) -> str:
    if behavior_score >= 0.45:
        return "Based on your recent activity"
    if related_score >= 0.5:
        return "Related to materials you recently opened"
    if course_score >= 0.4:
        return _course_reason(resource, user)
    if trending_score >= 0.6:
        return "Trending among students now"
    return "Recommended for you"


def get_ai_study_plan_recommendations(user, limit: int = 10):
    """
    AI-powered study plan recommendations based on user's learning progress.
    Analyzes user's course, year, and engagement to recommend study paths.
    """
    from django.db.models import Count, Avg
    from apps.resources.models import Resource
    from apps.courses.models import Course
    
    if not user or not user.is_authenticated:
        return []

    # Get user's academic context
    user_profile = getattr(user, 'profile', None)
    year_of_study = getattr(user_profile, 'year_of_study', None)
    course_id = getattr(user_profile, 'course_id', None)
    
    # Get resources user hasn't engaged with but are recommended for their course
    from .services import get_course_based_recommendations
    
    recommendations = []
    
    # Primary: Course-based recommendations
    if course_id:
        course_resources = get_course_based_recommendations(user, limit=limit * 2)
        recommendations.extend(course_resources[:limit])
    
    # Secondary: Related courses in same department
    if user_profile and user_profile.faculty_id:
        from apps.courses.models import Course
        related_courses = Course.objects.filter(
            department__faculty_id=user_profile.faculty_id
        ).exclude(id=course_id)[:3]
        
        for course in related_courses:
            course_recs = Resource.objects.filter(
                course=course,
                status='approved',
                is_public=True
            ).order_by('-download_count', '-average_rating')[:3]
            recommendations.extend(course_recs)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_recommendations = []
    for r in recommendations:
        if r.id not in seen:
            seen.add(r.id)
            unique_recommendations.append(r)
    
    return unique_recommendations[:limit]


def get_difficulty_analyzed_recommendations(user, limit: int = 10):
    """
    Recommend resources with difficulty analysis.
    Returns resources with estimated difficulty levels based on engagement metrics.
    """
    from apps.resources.models import Resource
    
    if not user or not user.is_authenticated:
        return []
    
    # Get resources with engagement analysis
    resources = Resource.objects.filter(
        status='approved',
        is_public=True
    ).select_related('course', 'faculty', 'department')
    
    # Annotate with engagement metrics
    resources = resources.annotate(
        engagement_score=Count('downloads') + 
                      Count('favorites') * 2 + 
                      Count('comments') * 3
    ).order_by('-engagement_score')
    
    return list(resources[:limit])


def get_learning_path_recommendations(user, topic: str, limit: int = 10):
    """
    Recommend a learning path for a specific topic.
    Returns ordered resources from beginner to advanced.
    """
    from apps.resources.models import Resource
    
    if not user or not user.is_authenticated:
        return []
    
    # Search for resources matching the topic
    resources = Resource.objects.filter(
        status='approved',
        is_public=True
    ).filter(
        Q(title__icontains=topic) |
        Q(description__icontains=topic) |
        Q(tags__icontains=topic)
    ).select_related('course')
    
    # Order by popularity as a proxy for difficulty progression
    resources = resources.order_by('-download_count', '-view_count', '-average_rating')
    
    return list(resources[:limit])
