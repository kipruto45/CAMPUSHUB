"""Services for search queries, indexing and recent-search history."""

from uuid import UUID

from django.db.models import (
    BooleanField,
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    Exists,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Cast
from django.utils import timezone

from apps.resources.models import Resource
from apps.search.models import RecentSearch, SearchIndex


class SearchService:
    """Service for search operations."""

    @staticmethod
    def normalize_query(query: str) -> str:
        return (query or "").strip().lower()

    @staticmethod
    def _split_csv(value):
        if value is None:
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _is_uuid(value) -> bool:
        try:
            UUID(str(value))
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def build_search_document(resource: Resource) -> str:
        """Build denormalized index text for a resource."""
        parts = [
            resource.title or "",
            resource.description or "",
            resource.tags or "",
            resource.resource_type or "",
            resource.file_type or "",
            getattr(resource.faculty, "name", ""),
            getattr(resource.department, "name", ""),
            getattr(resource.course, "name", ""),
            getattr(resource.course, "code", ""),
            getattr(resource.unit, "name", ""),
            getattr(resource.unit, "code", ""),
        ]
        return " ".join(part for part in parts if part).strip().lower()

    @staticmethod
    def upsert_resource_index(resource: Resource):
        """Create or update a resource index row for approved public content."""
        if resource.status != "approved" or not resource.is_public:
            SearchIndex.objects.filter(resource=resource).delete()
            return
        SearchIndex.objects.update_or_create(
            resource=resource,
            defaults={
                "search_document": SearchService.build_search_document(resource),
                "is_active": True,
                "indexed_at": timezone.now(),
            },
        )

    @staticmethod
    def remove_resource_index(resource: Resource):
        """Remove index row for a deleted or hidden resource."""
        SearchIndex.objects.filter(resource=resource).delete()

    @staticmethod
    def apply_filters(queryset, params: dict | None):
        """Apply all supported search filters."""
        params = params or {}
        queryset = queryset.filter(is_deleted=False)
        resource_types = SearchService._split_csv(params.get("resource_type"))
        if resource_types:
            queryset = queryset.filter(resource_type__in=resource_types)

        faculty = params.get("faculty")
        if faculty:
            if SearchService._is_uuid(faculty):
                queryset = queryset.filter(faculty_id=faculty)
            else:
                queryset = queryset.filter(
                    Q(faculty__name__icontains=str(faculty).strip())
                )

        department = params.get("department")
        if department:
            if SearchService._is_uuid(department):
                queryset = queryset.filter(department_id=department)
            else:
                queryset = queryset.filter(
                    Q(department__name__icontains=str(department).strip())
                )

        course = params.get("course")
        if course:
            if SearchService._is_uuid(course):
                queryset = queryset.filter(course_id=course)
            else:
                normalized_course = str(course).strip()
                queryset = queryset.filter(
                    Q(course__code__iexact=normalized_course)
                    | Q(course__name__icontains=normalized_course)
                )

        unit = params.get("unit")
        if unit:
            if SearchService._is_uuid(unit):
                queryset = queryset.filter(unit_id=unit)
            else:
                normalized_unit = str(unit).strip()
                queryset = queryset.filter(
                    Q(unit__code__iexact=normalized_unit)
                    | Q(unit__name__icontains=normalized_unit)
                )

        semester = params.get("semester")
        if semester:
            queryset = queryset.filter(semester=str(semester))

        year_of_study = params.get("year_of_study") or params.get("year")
        if year_of_study:
            queryset = queryset.filter(year_of_study=year_of_study)

        file_types = [
            item.lower().lstrip(".")
            for item in SearchService._split_csv(params.get("file_type"))
        ]
        if file_types:
            queryset = queryset.filter(file_type__in=file_types)

        return queryset

    @staticmethod
    def rank_search_results(queryset, query: str, user=None):
        """
        Annotate weighted relevance score.

        Score signals:
        - exact title match: 5
        - partial title match: 3
        - tag match: 2
        - course match: 2
        - unit match: 2
        - popularity boost: downloads + rating + favorites
        """
        normalized_query = SearchService.normalize_query(query)
        queryset = queryset.annotate(
            favorites_count=Count("favorites", distinct=True),
        )

        if normalized_query:
            query_filter = (
                Q(title__icontains=normalized_query)
                | Q(description__icontains=normalized_query)
                | Q(tags__icontains=normalized_query)
                | Q(course__name__icontains=normalized_query)
                | Q(course__code__icontains=normalized_query)
                | Q(unit__name__icontains=normalized_query)
                | Q(unit__code__icontains=normalized_query)
                | Q(search_index__search_document__icontains=normalized_query)
            )
            queryset = queryset.filter(query_filter)

        exact_title = Case(
            When(title__iexact=normalized_query, then=Value(5)),
            default=Value(0),
            output_field=IntegerField(),
        )
        partial_title = Case(
            When(title__icontains=normalized_query, then=Value(3)),
            default=Value(0),
            output_field=IntegerField(),
        )
        tag_match = Case(
            When(tags__icontains=normalized_query, then=Value(2)),
            default=Value(0),
            output_field=IntegerField(),
        )
        course_match = Case(
            When(
                Q(course__name__icontains=normalized_query)
                | Q(course__code__icontains=normalized_query),
                then=Value(2),
            ),
            default=Value(0),
            output_field=IntegerField(),
        )
        unit_match = Case(
            When(
                Q(unit__name__icontains=normalized_query)
                | Q(unit__code__icontains=normalized_query),
                then=Value(2),
            ),
            default=Value(0),
            output_field=IntegerField(),
        )
        popularity_score = ExpressionWrapper(
            F("download_count") * Value(0.05)
            + Cast(F("average_rating"), FloatField()) * Value(0.2)
            + F("favorites_count") * Value(0.12)
            + F("view_count") * Value(0.02),
            output_field=FloatField(),
        )
        base_relevance = ExpressionWrapper(
            exact_title + partial_title + tag_match + course_match + unit_match,
            output_field=FloatField(),
        )

        user_course_id = (
            getattr(user, "course_id", None) if user and user.is_authenticated else None
        )
        user_department_id = (
            getattr(user, "department_id", None)
            if user and user.is_authenticated
            else None
        )
        if user and user.is_authenticated and hasattr(user, "profile") and user.profile:
            user_course_id = user_course_id or getattr(user.profile, "course_id", None)
            user_department_id = user_department_id or getattr(
                user.profile, "department_id", None
            )

        academic_boost = (
            Case(
                When(course_id=user_course_id, then=Value(2.0)),
                default=Value(0.0),
                output_field=FloatField(),
            )
            + Case(
                When(department_id=user_department_id, then=Value(1.0)),
                default=Value(0.0),
                output_field=FloatField(),
            )
        )
        queryset = queryset.annotate(
            search_relevance=base_relevance,
            academic_boost=academic_boost,
            relevance_score=ExpressionWrapper(
                base_relevance + popularity_score + academic_boost,
                output_field=FloatField(),
            ),
        )
        return queryset

    @staticmethod
    def apply_sorting(queryset, sort_value: str | None):
        """Apply supported sorting options."""
        key = str(sort_value or "").strip().lower()
        sort_mapping = {
            "newest": "-created_at",
            "oldest": "created_at",
            "most_downloaded": "-download_count",
            "highest_rated": "-average_rating",
            "most_viewed": "-view_count",
            "most_favorited": "-favorites_count",
            "relevance": "-relevance_score",
        }
        if key in sort_mapping:
            return queryset.order_by(
                sort_mapping[key],
                "-relevance_score",
                "-download_count",
                "-created_at",
            )
        return queryset.order_by(
            "-relevance_score",
            "-academic_boost",
            "-download_count",
            "-view_count",
            "-average_rating",
            "-created_at",
        )

    @staticmethod
    def search_resources(query="", filters=None, user=None, sort=None, params=None):
        """Search approved public resources by query, filters and sorting."""
        if params is None and isinstance(query, dict):
            params = query
            query = params.get("q", params.get("search", ""))
            sort = params.get("sort", sort)
            filters = {
                "resource_type": params.get("resource_type"),
                "faculty": params.get("faculty"),
                "department": params.get("department"),
                "course": params.get("course"),
                "unit": params.get("unit"),
                "year_of_study": params.get("year_of_study")
                or params.get("year"),
                "semester": params.get("semester"),
                "file_type": params.get("file_type"),
            }

        queryset = Resource.objects.filter(status="approved", is_public=True).select_related(
            "uploaded_by",
            "faculty",
            "department",
            "course",
            "unit",
            "search_index",
        ).annotate(
            comments_count=Count("comments", distinct=True),
            ratings_count=Count("ratings", distinct=True),
        )

        if user and getattr(user, "is_authenticated", False):
            from apps.bookmarks.models import Bookmark
            from apps.favorites.models import Favorite, FavoriteType
            from apps.ratings.models import Rating

            queryset = queryset.annotate(
                is_bookmarked=Exists(
                    Bookmark.objects.filter(user=user, resource=OuterRef("pk"))
                ),
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=user,
                        favorite_type=FavoriteType.RESOURCE,
                        resource=OuterRef("pk"),
                    )
                ),
                user_rating=Subquery(
                    Rating.objects.filter(user=user, resource=OuterRef("pk"))
                    .values("value")[:1]
                ),
            )
        else:
            queryset = queryset.annotate(
                is_bookmarked=Value(False, output_field=BooleanField()),
                is_favorited=Value(False, output_field=BooleanField()),
                user_rating=Value(None, output_field=IntegerField()),
            )
        queryset = SearchService.apply_filters(queryset, filters)
        queryset = SearchService.rank_search_results(queryset, query, user=user)
        queryset = SearchService.apply_sorting(queryset, sort)
        return queryset.distinct()

    @staticmethod
    def save_recent_search(user, query: str, filters=None, results_count: int = 0):
        """Persist or update a recent search entry for authenticated users."""
        if not user or not user.is_authenticated:
            return None

        normalized_query = SearchService.normalize_query(query)
        if not normalized_query:
            return None

        recent, _ = RecentSearch.objects.update_or_create(
            user=user,
            normalized_query=normalized_query,
            defaults={
                "query": query.strip(),
                "filters": filters or {},
                "results_count": max(int(results_count or 0), 0),
                "last_searched_at": timezone.now(),
            },
        )
        return recent

    @staticmethod
    def get_recent_searches(user, limit=10):
        """Get recent search records for a user."""
        if not user or not user.is_authenticated:
            return RecentSearch.objects.none()
        return RecentSearch.objects.filter(user=user).order_by("-last_searched_at")[
            : max(1, limit)
        ]

    @staticmethod
    def delete_recent_search(user, recent_search_id):
        """Delete a single recent search item by id for owner."""
        return RecentSearch.objects.filter(user=user, id=recent_search_id).delete()[0]

    @staticmethod
    def search_by_course_name(query):
        """Search resources by course name."""
        return Resource.objects.filter(
            status="approved",
            is_public=True,
            course__name__icontains=query,
        )

    @staticmethod
    def search_by_unit_name(query):
        """Search resources by unit name."""
        return Resource.objects.filter(
            status="approved",
            is_public=True,
            unit__name__icontains=query,
        )

    @staticmethod
    def search_personal_files(query, user):
        """Search personal library files."""
        from apps.resources.models import PersonalResource

        queryset = PersonalResource.objects.filter(user=user)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(tags__icontains=query)
            )
        return queryset.order_by("-last_accessed_at", "-created_at")

    @staticmethod
    def build_search_suggestions(query, user=None, limit=10):
        """Get typed search suggestions from titles, courses, units and recent terms."""
        normalized_query = SearchService.normalize_query(query)
        if not normalized_query or len(normalized_query) < 2:
            return []

        suggestions: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add_item(label: str, item_type: str):
            clean = str(label or "").strip()
            key = (clean.lower(), item_type)
            if not clean or key in seen:
                return
            seen.add(key)
            suggestions.append({"value": clean, "type": item_type})

        base_qs = Resource.objects.filter(status="approved", is_public=True)

        for title in base_qs.filter(title__icontains=normalized_query).values_list(
            "title", flat=True
        )[:limit]:
            add_item(title, "title")

        for course_name in base_qs.filter(
            course__name__icontains=normalized_query
        ).values_list("course__name", flat=True)[:limit]:
            add_item(course_name, "course")

        for unit_name in base_qs.filter(unit__name__icontains=normalized_query).values_list(
            "unit__name", flat=True
        )[:limit]:
            add_item(unit_name, "unit")

        for tag_string in base_qs.filter(tags__icontains=normalized_query).values_list(
            "tags", flat=True
        )[:limit]:
            for tag in [t.strip() for t in (tag_string or "").split(",") if t.strip()]:
                if normalized_query in tag.lower():
                    add_item(tag, "tag")

        if user and user.is_authenticated:
            for recent_query in RecentSearch.objects.filter(
                user=user, normalized_query__icontains=normalized_query
            ).values_list("query", flat=True)[:limit]:
                add_item(recent_query, "recent")

        return suggestions[:limit]

    @staticmethod
    def get_suggestions(query, limit=10, user=None):
        """Backward-compatible plain string suggestions list."""
        return [
            item["value"]
            for item in SearchService.build_search_suggestions(
                query=query,
                user=user,
                limit=limit,
            )
        ]

    @staticmethod
    def get_trending_searches(limit=10):
        """Get trending search terms by frequency."""
        return (
            RecentSearch.objects.values("query")
            .annotate(search_count=Count("id"))
            .order_by("-search_count", "-last_searched_at")[: max(1, limit)]
        )
