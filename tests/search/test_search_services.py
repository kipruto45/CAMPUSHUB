"""Tests for search service-layer logic."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import PersonalResource, Resource
from apps.search.models import RecentSearch, SearchIndex
from apps.search.services import SearchService


def _resource(owner, **overrides):
    defaults = {
        "title": "Data Structures Notes",
        "description": "Stacks, queues, trees",
        "tags": "data-structures,algorithms,trees",
        "resource_type": "notes",
        "uploaded_by": owner,
        "status": "approved",
        "is_public": True,
    }
    defaults.update(overrides)
    return Resource.objects.create(**defaults)


@pytest.mark.django_db
def test_normalize_query_and_build_search_document(
    admin_user,
    faculty,
    department,
    course,
    unit,
):
    resource = _resource(
        admin_user,
        faculty=faculty,
        department=department,
        course=course,
        unit=unit,
        title="  Graph Theory Notes  ",
    )
    normalized = SearchService.normalize_query("  GRAPHS   ")
    document = SearchService.build_search_document(resource)

    assert normalized == "graphs"
    assert "graph theory notes" in document
    assert course.name.lower() in document
    assert unit.name.lower() in document


@pytest.mark.django_db
def test_upsert_and_remove_resource_index(admin_user):
    resource = _resource(admin_user, title="Index Me")
    SearchService.upsert_resource_index(resource)
    assert SearchIndex.objects.filter(resource=resource, is_active=True).exists()

    resource.status = "pending"
    resource.save(update_fields=["status"])
    SearchService.upsert_resource_index(resource)
    assert not SearchIndex.objects.filter(resource=resource).exists()

    resource.status = "approved"
    resource.is_public = True
    resource.save(update_fields=["status", "is_public"])
    SearchService.upsert_resource_index(resource)
    SearchService.remove_resource_index(resource)
    assert not SearchIndex.objects.filter(resource=resource).exists()


@pytest.mark.django_db
def test_search_resources_with_filters_sort_and_academic_boost(
    user,
    admin_user,
    faculty,
    department,
    course,
    unit,
):
    user.faculty = faculty
    user.department = department
    user.course = course
    user.save(update_fields=["faculty", "department", "course"])

    matched = _resource(
        admin_user,
        title="Data Structures Deep Dive",
        course=course,
        unit=unit,
        download_count=20,
        view_count=10,
    )
    _resource(
        admin_user,
        title="Chemistry Basics",
        resource_type="book",
        download_count=1,
        view_count=1,
    )
    SearchService.upsert_resource_index(matched)

    rows = SearchService.search_resources(
        query="data structures",
        filters={"resource_type": "notes", "course": course.id},
        user=user,
        sort="most_downloaded",
    )
    ids = list(rows.values_list("id", flat=True))

    assert matched.id in ids
    first = rows.first()
    assert hasattr(first, "search_relevance")
    assert hasattr(first, "academic_boost")


@pytest.mark.django_db
def test_search_resources_supports_course_code_and_file_type_filters(
    admin_user,
    course,
):
    course.code = "CSC101"
    course.save(update_fields=["code"])
    pdf = _resource(
        admin_user,
        title="Algorithm PDF",
        course=course,
        file_type="pdf",
        download_count=9,
    )
    _resource(
        admin_user,
        title="Algorithm DOCX",
        course=course,
        file_type="docx",
        download_count=50,
    )

    rows = SearchService.search_resources(
        query="algorithm",
        filters={"course": "CSC101", "file_type": "pdf"},
        sort="most_downloaded",
    )
    ids = list(rows.values_list("id", flat=True))

    assert ids == [pdf.id]


@pytest.mark.django_db
def test_search_resources_without_query_and_unknown_sort(admin_user):
    newest = _resource(admin_user, title="Newest")
    older = _resource(admin_user, title="Older")
    Resource.objects.filter(id=older.id).update(created_at="2025-01-01T00:00:00Z")

    rows = SearchService.search_resources(query="", sort="unknown")
    ids = list(rows.values_list("id", flat=True))

    assert newest.id in ids and older.id in ids
    assert rows.first().id == newest.id


@pytest.mark.django_db
def test_recent_and_trending_searches(user):
    first = SearchService.save_recent_search(
        user,
        "Data Structures",
        filters={"resource_type": "notes"},
        results_count=3,
    )
    second = SearchService.save_recent_search(user, "data structures", results_count=9)
    SearchService.save_recent_search(user, "Algorithms", results_count=5)

    assert first.id == second.id
    assert second.results_count == 9

    recent = SearchService.get_recent_searches(user, limit=2)
    assert recent.count() == 2

    trending = list(SearchService.get_trending_searches(limit=5))
    assert any(item["query"].lower() == "data structures" for item in trending)


@pytest.mark.django_db
def test_search_by_course_unit_personal_and_suggestions(
    user,
    admin_user,
    course,
    unit,
):
    course_match = _resource(
        admin_user,
        title="Course Match",
        course=course,
        unit=unit,
        tags="graphs,algorithms",
    )
    unit_match = _resource(
        admin_user,
        title="Unit Match",
        course=course,
        unit=unit,
        tags="trees,queues",
    )
    personal = PersonalResource.objects.create(
        user=user,
        title="Private Algorithms",
        description="my notes",
        tags="algorithms,private",
        file=SimpleUploadedFile("private.pdf", b"file"),
    )

    by_course = SearchService.search_by_course_name(course.name)
    by_unit = SearchService.search_by_unit_name(unit.name)
    personal_rows = SearchService.search_personal_files("private", user)
    suggestions = SearchService.get_suggestions("alg", limit=10)
    typed_suggestions = SearchService.build_search_suggestions("alg", user=user, limit=10)
    short = SearchService.get_suggestions("a", limit=10)

    assert course_match.id in set(by_course.values_list("id", flat=True))
    assert unit_match.id in set(by_unit.values_list("id", flat=True))
    assert personal_rows.first().id == personal.id
    assert "Course Match" in suggestions or "algorithms" in [
        value.lower() for value in suggestions
    ]
    assert any(item["type"] in {"title", "tag", "recent"} for item in typed_suggestions)
    assert short == []


@pytest.mark.django_db
def test_save_recent_search_ignores_anonymous_and_blank_query(user):
    class _Anon:
        is_authenticated = False

    assert SearchService.save_recent_search(_Anon(), "data", results_count=1) is None
    assert SearchService.save_recent_search(user, "   ", results_count=1) is None
    assert RecentSearch.objects.filter(user=user).count() == 0
