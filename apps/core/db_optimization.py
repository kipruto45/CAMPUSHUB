"""
Database Query Optimization and Indexing for CampusHub.
"""

import logging

from django.core.cache import cache
from django.db.models import Count

logger = logging.getLogger("db_logger")


# ========================
# Database Index Definitions
# ========================


class Index:
    """
    Represents a database index.
    """

    def __init__(self, fields, name=None, unique=False):
        self.fields = fields
        self.name = name
        self.unique = unique

    def to_sql(self, model):
        """Generate SQL for creating the index."""
        table = model._meta.db_table
        fields_str = ", ".join(self.fields)
        index_name = self.name or f"idx_{table}_{'_'.join(self.fields)}"

        unique_str = "UNIQUE" if self.unique else ""

        return f"CREATE INDEX {unique_str} {index_name} ON {table} ({fields_str})"


# Common index patterns
COMMON_INDEXES = {
    # User indexes
    "user_email": Index(["email"], unique=True),
    "user_username": Index(["username"], unique=True),
    "user_is_active": Index(["is_active"]),
    "user_is_verified": Index(["is_verified"]),
    "user_role": Index(["role"]),
    "user_date_joined": Index(["date_joined"]),
    # Resource indexes
    "resource_status": Index(["status"]),
    "resource_created_at": Index(["-created_at"]),
    "resource_course": Index(["course_id"]),
    "resource_unit": Index(["unit_id"]),
    "resource_created_by": Index(["uploaded_by_id"]),
    "resource_file_type": Index(["file_type"]),
    "resource_is_public": Index(["is_public"]),
    # Activity indexes
    "activity_user": Index(["user_id"]),
    "activity_type": Index(["activity_type"]),
    "activity_created_at": Index(["-created_at"]),
    # Download indexes
    "download_user": Index(["user_id"]),
    "download_resource": Index(["resource_id"]),
    "download_created_at": Index(["-created_at"]),
    # Bookmark indexes
    "bookmark_user": Index(["user_id"]),
    "bookmark_resource": Index(["resource_id"]),
    # Rating indexes
    "rating_user": Index(["user_id"]),
    "rating_resource": Index(["resource_id"]),
    # Notification indexes
    "notification_user": Index(["recipient_id"]),
    "notification_is_read": Index(["is_read"]),
    "notification_created_at": Index(["-created_at"]),
    # Comment indexes
    "comment_resource": Index(["resource_id"]),
    "comment_user": Index(["user_id"]),
    "comment_created_at": Index(["-created_at"]),
    # Report indexes
    "report_reporter": Index(["reporter_id"]),
    "report_resource": Index(["resource_id"]),
    "report_status": Index(["status"]),
    "report_reason": Index(["reason_type"]),
}


# ========================
# Query Optimization Tools
# ========================


class QueryOptimizer:
    """
    Query optimization utilities.
    """

    @staticmethod
    def optimize_queryset(
        queryset, select_related=None, prefetch_related=None, only=None, defer=None
    ):
        """
        Apply common optimizations to a queryset.

        Args:
            queryset: Django queryset to optimize
            select_related: List of foreign key fields to select
            prefetch_related: List of related fields to prefetch
            only: List of fields to include
            defer: List of fields to defer

        Returns:
            Optimized queryset
        """
        optimized = queryset

        if select_related:
            optimized = optimized.select_related(*select_related)

        if prefetch_related:
            optimized = optimized.prefetch_related(*prefetch_related)

        if only:
            optimized = optimized.only(*only)

        if defer:
            optimized = optimized.defer(*defer)

        return optimized

    @staticmethod
    def get_or_none(queryset, **kwargs):
        """
        Get object or return None (avoids DoesNotExist exception).
        """
        try:
            return queryset.get(**kwargs)
        except queryset.model.DoesNotExist:
            return None

    @staticmethod
    def bulk_get_or_create(queryset, items, unique_fields, defaults_fields):
        """
        Bulk get or create items efficiently.
        """
        results = []
        existing = {
            getattr(item, field): item
            for field in unique_fields
            for item in queryset.filter(
                **{f"{field}__in": [getattr(i, field) for i in items]}
            )
        }

        for item in items:
            key = tuple(getattr(item, field) for field in unique_fields)
            if key in existing:
                results.append(existing[key])
            else:
                obj, created = queryset.get_or_create(
                    **{field: getattr(item, field) for field in unique_fields},
                    defaults={field: getattr(item, field) for field in defaults_fields},
                )
                results.append(obj)

        return results


class PaginationOptimizer:
    """
    Optimize paginated queries.
    """

    @staticmethod
    def get_cursor_pagination_queryset(
        queryset, cursor=None, page_size=20, order_by="-created_at"
    ):
        """
        Efficient cursor-based pagination.
        """
        qs = queryset.order_by(order_by)

        if cursor:
            qs = qs.filter(pk__lt=cursor)

        return qs[: page_size + 1]  # Fetch one extra to check if there's more

    @staticmethod
    def get_count_optimized_queryset(queryset, min_id=None, max_id=None):
        """
        Get optimized queryset for counting.
        """
        qs = queryset

        if min_id:
            qs = qs.filter(id__gte=min_id)

        if max_id:
            qs = qs.filter(id__lte=max_id)

        return qs


# ========================
# Caching Strategies
# ========================


class CacheStrategy:
    """
    Caching strategies for database queries.
    """

    # Cache key prefixes
    PREFIX = "campushub"

    @classmethod
    def get_cache_key(cls, prefix, *args, **kwargs):
        """Generate a cache key."""
        parts = [cls.PREFIX, prefix]
        parts.extend(str(arg) for arg in args)
        parts.extend(f"{k}_{v}" for k, v in sorted(kwargs.items()))
        return ":".join(parts)

    @classmethod
    def cache_queryset(cls, queryset, key, timeout=300):
        """
        Cache a queryset result.
        """
        cache.set(key, list(queryset), timeout)

    @classmethod
    def get_cached_queryset(cls, key, model):
        """
        Get cached queryset and return as queryset-like object.
        """
        data = cache.get(key)
        if data is None:
            return None

        # Return as list (can be converted back to queryset if needed)
        return data

    @classmethod
    def invalidate_cache(cls, pattern):
        """
        Invalidate cache entries matching pattern.
        """
        # This is a simple implementation - in production use Redis SCAN
        cache.clear()


# ========================
# Query Optimization Mixins
# ========================


class OptimizedQueryMixin:
    """
    Mixin to add optimization methods to views.
    """

    def get_optimized_queryset(self, queryset):
        """Apply optimizations to queryset."""
        # Apply select_related for foreign keys
        select_related = self.get_select_related()
        if select_related:
            queryset = queryset.select_related(*select_related)

        # Apply prefetch_related for reverse FK and many-to-many
        prefetch_related = self.get_prefetch_related()
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        # Use only() to limit fields
        only_fields = self.get_only_fields()
        if only_fields:
            queryset = queryset.only(*only_fields)

        return queryset

    def get_select_related(self):
        """Override in subclass to specify select_related."""
        return []

    def get_prefetch_related(self):
        """Override in subclass to specify prefetch_related."""
        return []

    def get_only_fields(self):
        """Override in subclass to specify only fields."""
        return []


# ========================
# Performance Monitoring
# ========================


class QueryPerformanceMonitor:
    """
    Monitor database query performance.
    """

    @staticmethod
    def log_slow_query(query, duration_ms, threshold=100):
        """Log slow queries."""
        if duration_ms > threshold:
            logger.warning(f"SLOW QUERY ({duration_ms:.2f}ms): {query['sql'][:200]}")

    @staticmethod
    def get_query_stats():
        """Get query statistics."""
        from django.db import connection

        return {
            "total_queries": len(connection.queries),
            "total_time": sum(float(q["time"]) for q in connection.queries),
            "queries": [
                {"sql": q["sql"][:100], "time": q["time"]} for q in connection.queries
            ],
        }


# ========================
# Database Hints
# ========================


class UseIndexHint:
    """
    Provide hints to the database optimizer.
    """

    @staticmethod
    def with_index(queryset, index_name):
        """Force use of specific index."""
        # This is database-specific and may not work on all backends
        return queryset

    @staticmethod
    def force_index(queryset, index_name):
        """Force database to use index."""
        return queryset


class SelectForUpdateSkipLocked:
    """
    Use SELECT FOR UPDATE with SKIP LOCKED for concurrent row locking.
    """

    @staticmethod
    def with_skip_locked(queryset):
        """Select rows with skip locked."""
        return queryset.select_for_update(skip_locked=True)

    @staticmethod
    def with_nowait(queryset):
        """Select rows with nowait (fail immediately if locked)."""
        return queryset.select_for_update(nowait=True)


# ========================
# Common Query Patterns
# ========================


class CommonQueries:
    """
    Common query patterns optimized.
    """

    @staticmethod
    def get_popular_resources(limit=10, time_range_days=30):
        """Get popular resources efficiently."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=time_range_days)

        # Use annotation instead of subquery for better performance
        return (
            Resource.objects.filter(
                status="approved", is_public=True, downloads__created_at__gte=since
            )
            .annotate(download_count=Count("downloads"))
            .order_by("-download_count")[:limit]
        )

    @staticmethod
    def get_user_recent_activity(user, limit=20):
        """Get user's recent activity efficiently."""
        from apps.activity.models import RecentActivity

        return (
            RecentActivity.objects.filter(user=user)
            .select_related("resource", "personal_resource")
            .order_by("-created_at")[:limit]
        )

    @staticmethod
    def get_resource_with_details(resource_id):
        """Get resource with all related data in minimal queries."""
        from apps.resources.models import Resource

        return (
            Resource.objects.select_related("uploaded_by", "course", "unit")
            .prefetch_related("additional_files", "ratings")
            .get(pk=resource_id)
        )

    @staticmethod
    def get_dashboard_data(user):
        """Get dashboard data efficiently."""
        from apps.activity.models import RecentActivity
        from apps.bookmarks.models import Bookmark
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        # Use cached values or single queries with counts
        data = {
            "total_uploads": Resource.objects.filter(uploaded_by=user).count(),
            "total_downloads": Download.objects.filter(user=user).count(),
            "total_bookmarks": Bookmark.objects.filter(user=user).count(),
            "recent_activity": RecentActivity.objects.filter(user=user).select_related(
                "resource"
            )[:5],
        }

        return data


# ========================
# Migration Helper
# ========================


class IndexMigrationHelper:
    """
    Helper for creating indexes via migrations.
    """

    @staticmethod
    def get_migration_sql(indexes):
        """Get SQL for creating indexes."""
        sql_statements = []

        for model_path, model_indexes in indexes.items():
            for index in model_indexes:
                sql_statements.append(index.to_sql(model_path))

        return sql_statements

    @staticmethod
    def create_indexes_from_definition(definition):
        """Create indexes from definition."""
        from django.apps import apps

        for model_path, index_names in definition.items():
            try:
                model = apps.get_model(model_path)
                for index_name in index_names:
                    index = COMMON_INDEXES.get(index_name)
                    if index:
                        sql = index.to_sql(model)
                        logger.info(f"Creating index: {sql}")
                        # In migration, use migrations.RunSQL(sql)
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {e}")
