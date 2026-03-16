"""Tests for OOP recommendation strategy services."""
import pytest

from apps.downloads.models import Download
from apps.recommendations.oop_services import (
    BehaviorBasedRecommender,
    CourseBasedRecommender,
    RecommendationService,
    TrendingRecommender,
)
from apps.resources.models import Resource


@pytest.mark.django_db
class TestRecommendationOOPServices:
    """Strategy/factory behavior for OOP recommenders."""

    def test_get_recommender_defaults_to_trending(self):
        recommender = RecommendationService.get_recommender('unknown-type')
        assert isinstance(recommender, TrendingRecommender)

    def test_course_based_recommender_prioritizes_course_match(
        self, user, admin_user, faculty, department, course, unit
    ):
        user.faculty = faculty
        user.department = department
        user.course = course
        user.year_of_study = 2
        user.semester = 1
        user.save(update_fields=['faculty', 'department', 'course', 'year_of_study', 'semester'])

        matched = Resource.objects.create(
            title='Matched Resource',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            year_of_study=2,
            semester='1',
            download_count=2,
        )
        unmatched = Resource.objects.create(
            title='Unmatched Resource',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
            year_of_study=4,
            semester='2',
            download_count=2,
        )

        rows = CourseBasedRecommender().recommend(user, limit=10)
        assert rows
        ids = [row.id for row in rows]
        assert matched.id in ids
        assert ids.index(matched.id) < ids.index(unmatched.id)

    def test_behavior_recommender_excludes_consumed_resources(
        self, user, admin_user, faculty, department, course, unit
    ):
        user.faculty = faculty
        user.department = department
        user.course = course
        user.year_of_study = 2
        user.semester = 1
        user.save(update_fields=['faculty', 'department', 'course', 'year_of_study', 'semester'])

        consumed = Resource.objects.create(
            title='Consumed',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags='trees,graphs',
        )
        candidate = Resource.objects.create(
            title='Candidate',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags='trees,queues',
        )

        Download.objects.create(user=user, resource=consumed)
        rows = BehaviorBasedRecommender().recommend(user, limit=10)
        ids = [row.id for row in rows]

        assert consumed.id not in ids
        assert candidate.id in ids

    def test_hybrid_recommendations_are_deduplicated(self, user, admin_user, faculty, department, course, unit):
        user.faculty = faculty
        user.department = department
        user.course = course
        user.save(update_fields=['faculty', 'department', 'course'])

        for i in range(1, 5):
            Resource.objects.create(
                title=f'Resource {i}',
                resource_type='notes',
                uploaded_by=admin_user,
                status='approved',
                is_public=True,
                faculty=faculty,
                department=department,
                course=course,
                unit=unit,
                tags='algorithms,data-structures',
                view_count=i * 5,
                download_count=i * 3,
            )

        rows = RecommendationService.get_hybrid_recommendations(user, limit=10)
        ids = [row.id for row in rows]

        assert rows
        assert len(ids) == len(set(ids))
        assert all(hasattr(row, 'hybrid_score') for row in rows)
