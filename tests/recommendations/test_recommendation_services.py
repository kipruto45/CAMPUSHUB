"""Unit tests for recommendation service algorithms and caching."""

from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.recommendations.models import RecommendationCache, UserInterestProfile
from apps.recommendations import services
from apps.resources.models import Resource


def _resource(
    owner,
    *,
    title,
    resource_type="notes",
    status="approved",
    is_public=True,
    tags="",
    faculty=None,
    department=None,
    course=None,
    unit=None,
    year_of_study=None,
    semester="",
    view_count=0,
    download_count=0,
    average_rating=0,
):
    return Resource.objects.create(
        title=title,
        resource_type=resource_type,
        status=status,
        is_public=is_public,
        tags=tags,
        uploaded_by=owner,
        faculty=faculty,
        department=department,
        course=course,
        unit=unit,
        year_of_study=year_of_study,
        semester=semester,
        view_count=view_count,
        download_count=download_count,
        average_rating=average_rating,
    )


def _fake_resource(**overrides):
    baseline = {
        "tags": "trees, queues",
        "title": "Data Structures Notes",
        "description": "Great notes for algorithms and trees",
        "resource_type": "notes",
        "course": SimpleNamespace(name="Computer Science"),
        "unit": SimpleNamespace(name="Data Structures"),
        "created_at": timezone.now() - timedelta(days=2),
        "view_count": 10,
        "download_events_count": 5,
        "bookmark_events_count": 2,
        "favorite_events_count": 3,
        "rating_avg": 4.0,
        "course_id": 1,
        "department_id": 1,
        "faculty_id": 1,
        "unit_id": 1,
        "year_of_study": 2,
        "semester": "1",
        "id": "resource-1",
    }
    baseline.update(overrides)
    return SimpleNamespace(**baseline)


@pytest.mark.django_db
def test_tokenization_and_tag_helpers():
    tokens = services._tokenize_text(
        "The introduction to Data Structures, and Algorithms in Python!"
    )
    tags = services._resource_tags(_fake_resource(tags="python, data , , trees"))
    interest_tokens = services._resource_interest_tokens(_fake_resource())

    assert "the" not in tokens
    assert "data" in tokens
    assert tags == {"python", "data", "trees"}
    assert "structures" in interest_tokens
    assert "notes" in interest_tokens


@pytest.mark.django_db
def test_cosine_similarity_and_behavior_summary_helpers():
    similarity = services._cosine_similarity_sparse(
        {"algorithms": 2.0, "trees": 3.0},
        {"trees", "queues"},
    )
    empty_similarity = services._cosine_similarity_sparse({}, {"trees"})

    profile = {
        "viewed_resource_ids": {"a", "b"},
        "viewed_courses": {1},
        "viewed_units": {2},
        "downloaded_tags": {"algorithms"},
        "bookmarked_types": {"notes"},
        "favorite_tags": {"trees"},
        "high_rated_resource_ids": {"x"},
    }
    summary = services._behavior_summary_from_profile(profile)

    assert 0 < similarity <= 1
    assert empty_similarity == 0
    assert summary["viewed_count"] == 2
    assert summary["downloaded_tags"] == ["algorithms"]


@pytest.mark.django_db
def test_academic_period_mapping(monkeypatch):
    month_map = {
        4: "exam",
        3: "project",
        1: "revision",
        2: "beginning",
        10: "default",
    }
    for month, expected in month_map.items():
        mocked_now = datetime(2026, month, 10, tzinfo=dt_timezone.utc)
        monkeypatch.setattr(
            services.timezone,
            "now",
            lambda m=mocked_now: m,
        )
        assert services._get_current_academic_period() == expected

    assert services._get_period_reason("exam") == "Essential for exam preparation"
    assert services._get_period_reason("unknown") == "Recommended for you"


@pytest.mark.django_db
def test_seasonal_weight_and_scoring_helpers(monkeypatch):
    exam_resource = _fake_resource(
        title="Past Paper Questions",
        description="Exam revision resource",
    )
    monkeypatch.setattr(services, "_get_current_academic_period", lambda: "exam")
    seasonal_weight = services._get_seasonal_weight(exam_resource)

    trending_score = services.calculate_trending_score(exam_resource)
    popularity_score = services.calculate_popularity_score(exam_resource)

    assert seasonal_weight == services.SEASONAL_EXAM_PERIOD_WEIGHT
    assert trending_score > 0
    assert popularity_score > 0


@pytest.mark.django_db
def test_popularity_reason_course_reason_related_score_and_hybrid_reason(user):
    resource = _fake_resource(download_events_count=20, favorite_events_count=1)
    reason = services.get_popularity_reason(resource)
    assert reason == "Most downloaded by students"

    user.faculty_id = 1
    user.department_id = 1
    user.course_id = 1
    user.year_of_study = 2
    course_reason = services._course_reason(_fake_resource(), user)
    course_score = services.calculate_course_match_score(_fake_resource(), user)

    related_score = services.calculate_related_score(
        _fake_resource(id="source", tags="trees,queues"),
        _fake_resource(id="candidate", tags="trees,graphs"),
    )
    hybrid_reason = services._build_hybrid_reason(
        _fake_resource(),
        user,
        behavior_score=0.2,
        course_score=0.6,
        trending_score=0.1,
        related_score=0.1,
    )

    assert course_reason == "Matches your course and year"
    assert course_score > 0
    assert related_score >= services.RELATED_TAG_WEIGHT
    assert hybrid_reason == "Matches your course and year"


@pytest.mark.django_db
def test_recommendation_reason_precedence(user):
    explicit = _fake_resource(recommendation_reason="Because you saved similar")
    fallback = _fake_resource(
        recommendation_reason="",
        download_events_count=0,
        average_rating=4.8,
        course_id=999,
        department_id=999,
        faculty_id=999,
    )
    user.course_id = None
    user.department_id = None
    user.faculty_id = None

    assert services.get_recommendation_reason(explicit, user) == (
        "Because you saved similar"
    )
    assert services.get_recommendation_reason(fallback, user) == (
        "Highly rated by learners"
    )


@pytest.mark.django_db
def test_cache_roundtrip_and_invalidations(user, admin_user):
    item_one = _resource(admin_user, title="Cache Item One")
    item_two = _resource(admin_user, title="Cache Item Two")
    item_one.final_score = 0.9
    item_two.final_score = 0.8
    item_one.recommendation_reason = "High signal"
    item_two.recommendation_reason = "Medium signal"

    services._cache_recommendations(
        user,
        RecommendationCache.CATEGORY_FOR_YOU,
        [item_one, item_two],
        ttl_hours=1,
    )
    cached = services._get_cached_recommendations(
        user,
        RecommendationCache.CATEGORY_FOR_YOU,
        limit=5,
    )
    assert len(cached) == 2
    assert float(cached[0].final_score) > 0

    services.invalidate_user_recommendation_cache(
        user,
        categories=[RecommendationCache.CATEGORY_FOR_YOU],
    )
    assert RecommendationCache.objects.filter(user=user).count() == 0

    services._cache_recommendations(
        user,
        RecommendationCache.CATEGORY_FOR_YOU,
        [item_one],
        ttl_hours=1,
    )
    services.invalidate_resource_recommendation_cache(item_one)
    assert RecommendationCache.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_download_based_recommendations_with_cache(user, admin_user, course, unit):
    source = _resource(
        admin_user,
        title="Downloaded Source",
        tags="trees,graphs",
        course=course,
        unit=unit,
        resource_type="notes",
    )
    candidate = _resource(
        admin_user,
        title="Matching Candidate",
        tags="trees,queues",
        course=course,
        unit=unit,
        resource_type="notes",
    )
    _resource(admin_user, title="Unrelated", tags="history", resource_type="book")
    Download.objects.create(user=user, resource=source)

    rows = services.get_download_based_recommendations(user, limit=5)
    ids = [row.id for row in rows]

    assert candidate.id in ids
    assert source.id not in ids
    assert RecommendationCache.objects.filter(
        user=user,
        category=RecommendationCache.CATEGORY_DOWNLOAD,
    ).exists()


@pytest.mark.django_db
def test_saved_based_recommendations_with_cache(user, admin_user, course, unit):
    source = _resource(
        admin_user,
        title="Saved Source",
        tags="algorithms,trees",
        course=course,
        unit=unit,
    )
    candidate = _resource(
        admin_user,
        title="Saved Related Candidate",
        tags="algorithms,graphs",
        course=course,
        unit=unit,
    )
    Bookmark.objects.create(user=user, resource=source)
    Favorite.objects.create(
        user=user,
        favorite_type=FavoriteType.RESOURCE,
        resource=source,
    )

    rows = services.get_saved_based_recommendations(user, limit=5)
    ids = [row.id for row in rows]

    assert candidate.id in ids
    assert source.id not in ids
    assert RecommendationCache.objects.filter(
        user=user,
        category=RecommendationCache.CATEGORY_SAVED,
    ).exists()


@pytest.mark.django_db
def test_for_you_recommendations_uses_cache_when_available(user, admin_user):
    resource = _resource(admin_user, title="Cached For You")
    RecommendationCache.objects.create(
        user=user,
        resource=resource,
        category=RecommendationCache.CATEGORY_FOR_YOU,
        score=0.77,
        reason="Cached reason",
        rank=1,
        expires_at=timezone.now() + timedelta(hours=2),
    )

    with patch("apps.recommendations.services.get_trending_resources") as mocked:
        rows = services.get_for_you_recommendations(user, limit=1)

    assert len(rows) == 1
    assert rows[0].id == resource.id
    mocked.assert_not_called()


@pytest.mark.django_db
def test_for_you_recommendations_computes_and_caches(user, admin_user):
    candidate = _resource(admin_user, title="Computed For You")
    get_personalized = (
        "apps.recommendations.services.get_personalized_recommendations"
    )
    calc_course = "apps.recommendations.services.calculate_course_match_score"
    calc_behavior = "apps.recommendations.services.calculate_behavior_score"
    calc_trending = "apps.recommendations.services.calculate_trending_score"
    ai_similarity = "apps.recommendations.services._ai_similarity_proxy"

    with patch(
        "apps.recommendations.services.get_user_behavior_profile",
        return_value={
            "viewed_resource_ids": set(),
            "viewed_courses": set(),
            "viewed_units": set(),
            "downloaded_tags": set(),
            "bookmarked_types": set(),
            "favorite_tags": set(),
            "high_rated_resource_ids": set(),
        },
    ):
        with patch("apps.recommendations.services.refresh_user_interest_profile"):
            with patch(
                "apps.recommendations.services.get_trending_resources",
                return_value=[candidate],
            ):
                with patch(
                    "apps.recommendations.services.get_course_based_recommendations",
                    return_value=[candidate],
                ):
                    with patch(get_personalized, return_value=[candidate]):
                        with patch(calc_course, return_value=5.0):
                            with patch(calc_behavior, return_value=0.4):
                                with patch(calc_trending, return_value=2.0):
                                    with patch(ai_similarity, return_value=0.3):
                                        rows = services.get_for_you_recommendations(
                                            user,
                                            limit=1,
                                        )

    assert len(rows) == 1
    assert rows[0].id == candidate.id
    assert RecommendationCache.objects.filter(
        user=user,
        category=RecommendationCache.CATEGORY_FOR_YOU,
    ).exists()


@pytest.mark.django_db
def test_interest_profile_refresh_and_ai_similarity(user, admin_user, course, unit):
    source = _resource(
        admin_user,
        title="Trees and Queues",
        tags="trees,queues",
        course=course,
        unit=unit,
    )
    Download.objects.create(user=user, resource=source)

    profile = services.refresh_user_interest_profile(user)
    assert profile is not None
    assert UserInterestProfile.objects.filter(user=user).exists()

    candidate = _resource(
        admin_user,
        title="Advanced Trees",
        tags="trees,binary",
        course=course,
        unit=unit,
    )
    behavior_profile = services.get_user_behavior_profile(user)
    score = services._ai_similarity_proxy(candidate, behavior_profile, user=user)
    assert 0 <= score <= 1
