"""Tests for core algorithms (trees, scoring, ranking, deduplication)."""
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.activity.models import ActivityType, RecentActivity
from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
from apps.core.algorithms import (
    aggregate_course_usage,
    aggregate_faculty_usage,
    aggregate_resource_metrics,
    aggregate_user_activity,
    aggregate_usage_dictionaries,
    build_comment_tree,
    calculate_resource_score,
    calculate_recommendation_score,
    calculate_related_resource_similarity,
    calculate_search_relevance,
    deduplicate_resources,
    detect_duplicate_bookmark,
    detect_duplicate_favorite,
    detect_duplicate_filename,
    detect_duplicate_report,
    detect_duplicate_resource_upload,
    get_all_descendant_folders,
    get_breadcrumbs,
    get_folder_depth,
    get_folder_tree,
    rank_analytics_entities,
    rank_resources_by_score,
    sort_resources_by_criteria,
    traverse_comment_tree,
    validate_academic_hierarchy,
    validate_circular_folder_reference,
    validate_file_type,
    validate_folder_move,
    validate_storage_quota,
)
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.ratings.models import Rating
from apps.reports.models import Report
from apps.resources.models import PersonalFolder, PersonalResource, Resource, UserStorage


@pytest.mark.django_db
class TestTreeAlgorithms:
    """Folder and comment tree algorithms."""

    def test_validate_folder_move_blocks_invalid_moves(self, user, admin_user):
        root = PersonalFolder.objects.create(user=user, name='Root')
        child = PersonalFolder.objects.create(user=user, name='Child', parent=root)
        grandchild = PersonalFolder.objects.create(user=user, name='Grandchild', parent=child)
        other_user_folder = PersonalFolder.objects.create(user=admin_user, name='Other User Folder')

        ok, err = validate_folder_move(root, root, user)
        assert not ok
        assert 'itself' in err.lower()

        ok, err = validate_folder_move(root, grandchild, user)
        assert not ok
        assert 'descendant' in err.lower()

        ok, err = validate_folder_move(root, other_user_folder, user)
        assert not ok
        assert "another user's folder" in err.lower()

        ok, err = validate_folder_move(child, None, user)
        assert ok
        assert err is None

    def test_comment_tree_build_and_traverse(self, user, faculty, department, course, unit):
        resource = Resource.objects.create(
            title='Algorithms Notes',
            resource_type='notes',
            uploaded_by=user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
        )
        root = Comment.objects.create(user=user, resource=resource, content='Root')
        Comment.objects.create(user=user, resource=resource, parent=root, content='Reply')
        Comment.objects.create(user=user, resource=resource, parent=root, content='Hidden', is_deleted=True)
        Comment.objects.create(user=user, resource=resource, content='Second root')

        tree = build_comment_tree(resource)
        assert len(tree) == 2  # deleted child excluded by default

        flat = traverse_comment_tree(tree)
        assert [row['depth'] for row in flat] == [0, 1, 0]

        tree_with_deleted = build_comment_tree(resource, include_deleted=True)
        flat_with_deleted = traverse_comment_tree(tree_with_deleted)
        deleted_rows = [row for row in flat_with_deleted if row['is_deleted']]
        assert deleted_rows
        assert deleted_rows[0]['content'] == '[deleted]'


@pytest.mark.django_db
class TestScoringAndRankingAlgorithms:
    """Recommendation/search similarity and analytics ranking algorithms."""

    def test_related_similarity_and_search_relevance(self, user, faculty, department, course, unit):
        target = Resource.objects.create(
            title='Data Structures Notes',
            description='Trees and graphs',
            resource_type='notes',
            uploaded_by=user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags='trees,graphs,algorithms',
        )
        candidate = Resource.objects.create(
            title='Advanced Trees',
            description='Binary tree techniques',
            resource_type='notes',
            uploaded_by=user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags='trees,optimization',
        )

        similarity = calculate_related_resource_similarity(target, candidate)
        assert similarity == 11  # unit(5) + course(3) + overlap(2) + type(1)

        exact = calculate_search_relevance(target, 'data structures notes')
        partial = calculate_search_relevance(target, 'trees')
        missing = calculate_search_relevance(target, 'quantum mechanics')
        assert exact > partial > missing

    def test_recommendation_score_with_profile_and_behavior(self, user, faculty, department, course, unit):
        resource = Resource.objects.create(
            title='Course Match Resource',
            resource_type='notes',
            uploaded_by=user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            view_count=20,
            download_count=10,
            average_rating=4.5,
        )
        resource.favorite_count = 4

        base = calculate_recommendation_score(resource)
        profile = {
            'faculty_id': faculty.id,
            'department_id': department.id,
            'course_id': course.id,
            'year_of_study': 2,
            'semester': 1,
        }
        behavior = {
            'consumed_ids': set(),
            'preferred_courses': {course.id},
            'preferred_units': {unit.id},
        }
        boosted = calculate_recommendation_score(resource, user_profile=profile, behavior=behavior)
        assert boosted > base

        penalized = calculate_recommendation_score(
            resource,
            user_profile=profile,
            behavior={
                'consumed_ids': {resource.id},
                'preferred_courses': set(),
                'preferred_units': set(),
            },
        )
        assert penalized < boosted

    def test_analytics_dictionaries_ranking_and_dedup(self, user, admin_user, faculty, department, course, unit):
        user.faculty = faculty
        user.save(update_fields=['faculty'])
        admin_user.faculty = faculty
        admin_user.save(update_fields=['faculty'])

        first = Resource.objects.create(
            title='First Resource',
            resource_type='notes',
            uploaded_by=user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            view_count=40,
            download_count=12,
        )
        second = Resource.objects.create(
            title='Second Resource',
            resource_type='notes',
            uploaded_by=admin_user,
            status='approved',
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            view_count=10,
            download_count=8,
        )

        Favorite.objects.create(user=user, favorite_type=FavoriteType.RESOURCE, resource=first)
        RecentActivity.objects.create(
            user=user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            resource=first,
        )
        RecentActivity.objects.create(
            user=admin_user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            resource=second,
        )

        metrics = aggregate_usage_dictionaries(days=30)
        assert metrics['downloads_by_course'][course.name] == 20
        assert metrics['views_by_unit'][unit.name] == 50
        assert metrics['favorites_by_resource'][first.title] == 1
        assert metrics['active_users_by_faculty'][faculty.name] == 2

        ranking = rank_analytics_entities({'A': 4, 'B': 9, 'C': 2}, limit=2)
        assert ranking == [('B', 9), ('A', 4)]

        deduped = deduplicate_resources([first, first, second, first])
        assert [row.id for row in deduped] == [first.id, second.id]


@pytest.mark.django_db
class TestAdditionalAlgorithmCoverage:
    """Additional algorithm coverage for utility and validation paths."""

    def test_folder_tree_breadcrumbs_and_depth(self, user):
        root = PersonalFolder.objects.create(user=user, name="Root")
        child = PersonalFolder.objects.create(user=user, name="Child", parent=root)
        PersonalResource.objects.create(
            user=user,
            folder=child,
            title="Child File",
            file=SimpleUploadedFile("child_file.pdf", b"%PDF-1.4 child"),
        )

        tree_without_files = get_folder_tree(user, include_files=False)
        root_node = next(item for item in tree_without_files if item["name"] == "Root")
        assert "files" not in root_node

        tree_with_files = get_folder_tree(user, include_files=True)
        root_with_files = next(item for item in tree_with_files if item["name"] == "Root")
        child_node = next(item for item in root_with_files["subfolders"] if item["name"] == "Child")
        assert child_node["files"][0]["title"] == "Child File"

        breadcrumbs = get_breadcrumbs(child)
        breadcrumbs_without_current = get_breadcrumbs(child, include_current=False)
        assert [item["name"] for item in breadcrumbs] == ["Root", "Child"]
        assert [item["name"] for item in breadcrumbs_without_current] == ["Root"]

        descendants = get_all_descendant_folders(root)
        assert child.id in descendants
        assert get_folder_depth(root) == 0
        assert get_folder_depth(child) == 1

    def test_duplicate_detection_algorithms(
        self, user, faculty, department, course, unit
    ):
        resource = Resource.objects.create(
            title="Duplicate Detection Notes",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags="duplicates,algorithms",
        )

        assert detect_duplicate_bookmark(user, resource.id) is False
        Bookmark.objects.create(user=user, resource=resource)
        assert detect_duplicate_bookmark(user, resource.id) is True

        assert detect_duplicate_favorite(user, resource.id) is False
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        assert detect_duplicate_favorite(user, resource.id) is True

        Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="duplicate",
            message="same content",
        )
        assert detect_duplicate_report(user, resource.id, "duplicate") is True

        assert detect_duplicate_filename(user, "My File") is False
        root_file = PersonalResource.objects.create(
            user=user,
            title="My File",
            file=SimpleUploadedFile("my_file.pdf", b"%PDF-1.4 root"),
        )
        assert detect_duplicate_filename(user, "my file") is True
        assert detect_duplicate_filename(
            user,
            "my file",
            exclude_resource_id=root_file.id,
        ) is False

        folder = PersonalFolder.objects.create(user=user, name="Algorithms")
        PersonalResource.objects.create(
            user=user,
            folder=folder,
            title="Folder File",
            file=SimpleUploadedFile("folder_file.pdf", b"%PDF-1.4 folder"),
        )
        assert detect_duplicate_filename(user, "Folder File", folder=folder) is True
        assert detect_duplicate_filename(user, "Folder File") is False

        duplicates = detect_duplicate_resource_upload(
            user=user,
            course_id=course.id,
            unit_id=unit.id,
            title="Duplicate Detection Notes",
        )
        assert duplicates.filter(id=resource.id).exists()

    def test_aggregation_and_validation_algorithms(
        self, user, faculty, department, course, unit
    ):
        resource = Resource.objects.create(
            title="Aggregation Resource",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            view_count=14,
            download_count=7,
            average_rating=4.0,
        )
        Download.objects.create(user=user, resource=resource)
        Bookmark.objects.create(user=user, resource=resource)
        Favorite.objects.create(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            resource=resource,
        )
        Rating.objects.create(user=user, resource=resource, value=4)
        RecentActivity.objects.create(
            user=user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            resource=resource,
        )

        activity = aggregate_user_activity(user, days=30)
        assert activity == {
            "views": 1,
            "downloads": 1,
            "bookmarks": 1,
            "favorites": 1,
            "ratings": 1,
        }

        metrics = aggregate_resource_metrics([resource.id])
        assert metrics["total_resources"] == 1
        assert metrics["total_downloads"] == 1
        assert metrics["total_bookmarks"] == 1
        assert metrics["total_favorites"] == 1
        assert metrics["avg_rating"] == 4

        faculty_usage = aggregate_faculty_usage()
        course_usage = aggregate_course_usage()
        assert faculty_usage[0]["faculty__name"] == faculty.name
        assert course_usage[0]["course__name"] == course.name
        assert (
            course_usage[0]["course__department__faculty__name"] == faculty.name
        )

        folder = PersonalFolder.objects.create(user=user, name="Root")
        child = PersonalFolder.objects.create(user=user, name="Child", parent=folder)
        assert validate_circular_folder_reference(folder, None) is True
        assert validate_circular_folder_reference(folder, folder) is False
        assert validate_circular_folder_reference(folder, child) is False

        storage, _ = UserStorage.objects.get_or_create(user=user)
        assert validate_storage_quota(user, 1024)[0] is True
        assert validate_storage_quota(user, storage.storage_limit + 1)[0] is False

        valid = validate_academic_hierarchy(
            faculty.id, department.id, course.id, unit.id
        )
        assert valid == (True, None)
        invalid = validate_academic_hierarchy(None, None, None, uuid4())
        assert invalid[0] is False

        assert validate_file_type("PDF") is True
        assert validate_file_type("exe") is False

    def test_sorting_and_ranking_algorithms(self, user, faculty, department, course, unit):
        first = Resource.objects.create(
            title="A Resource",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            view_count=5,
            download_count=2,
            average_rating=3.0,
            file_size=100,
        )
        second = Resource.objects.create(
            title="Z Resource",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            view_count=50,
            download_count=20,
            average_rating=4.8,
            file_size=200,
        )

        by_download = sort_resources_by_criteria([first, second], "most_downloaded")
        by_name = sort_resources_by_criteria([first, second], "name", ascending=True)
        assert [r.id for r in by_download] == [second.id, first.id]
        assert [r.id for r in by_name] == [first.id, second.id]

        score_first = calculate_resource_score(first)
        score_second = calculate_resource_score(second)
        assert score_second > score_first

        ranked = rank_resources_by_score([first, second])
        assert [r.id for r in ranked] == [second.id, first.id]

        assert rank_analytics_entities({}, limit=5) == []
