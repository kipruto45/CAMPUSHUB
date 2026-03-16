"""
Filters for resources app.
"""

import django_filters

from .models import Resource


class ResourceFilter(django_filters.FilterSet):
    """Filter for Resource model."""

    title = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    resource_type = django_filters.ChoiceFilter(choices=Resource.RESOURCE_TYPE_CHOICES)
    faculty = django_filters.UUIDFilter(field_name="faculty_id")
    department = django_filters.UUIDFilter(field_name="department_id")
    course = django_filters.UUIDFilter(field_name="course_id")
    unit = django_filters.UUIDFilter(field_name="unit_id")
    semester = django_filters.ChoiceFilter(
        choices=[("1", "Semester 1"), ("2", "Semester 2")]
    )
    year_of_study = django_filters.NumberFilter()
    status = django_filters.ChoiceFilter(choices=Resource.STATUS_CHOICES)
    uploaded_by = django_filters.UUIDFilter(field_name="uploaded_by_id")
    tags = django_filters.CharFilter(method="filter_by_tags")
    min_downloads = django_filters.NumberFilter(
        field_name="download_count", lookup_expr="gte"
    )
    max_downloads = django_filters.NumberFilter(
        field_name="download_count", lookup_expr="lte"
    )
    min_views = django_filters.NumberFilter(field_name="view_count", lookup_expr="gte")
    max_views = django_filters.NumberFilter(field_name="view_count", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(
        field_name="average_rating", lookup_expr="gte"
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",
            "resource_type",
            "faculty",
            "department",
            "course",
            "unit",
            "semester",
            "year_of_study",
            "status",
            "uploaded_by",
            "tags",
            "is_public",
        ]

    def filter_by_tags(self, queryset, name, value):
        """Filter by tags."""
        tags = [tag.strip() for tag in value.split(",")]
        for tag in tags:
            queryset = queryset.filter(tags__icontains=tag)
        return queryset


class OrderingFilter(django_filters.OrderingFilter):
    """Custom ordering filter."""

    ordering_fields = [
        ("created_at", "newest"),
        ("-created_at", "oldest"),
        ("download_count", "most_downloaded"),
        ("-download_count", "least_downloaded"),
        ("view_count", "most_viewed"),
        ("-view_count", "least_viewed"),
        ("average_rating", "highest_rated"),
        ("-average_rating", "lowest_rated"),
        ("title", "title_asc"),
        ("-title", "title_desc"),
    ]
