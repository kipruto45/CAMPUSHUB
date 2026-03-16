"""
Core algorithms for CampusHub platform.

This module provides reusable algorithms for:
- Tree traversal (folders, breadcrumbs)
- Duplicate detection (bookmarks, favorites, reports)
- Aggregation (analytics, metrics)
- Validation (permissions, quotas, circular references)
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

# ==================== TREE TRAVERSAL ALGORITHMS ====================


def get_folder_tree(user, root_folder=None, include_files=True):
    """
    Build a tree structure for folders using recursive traversal.

    Algorithm: Depth-First Search (DFS)

    Args:
        user: The user who owns the folders
        root_folder: Optional root folder to start from
        include_files: Whether to include files in each folder

    Returns:
        List of folder trees with nested subfolders
    """
    from apps.resources.models import PersonalFolder, PersonalResource

    if root_folder:
        folders = PersonalFolder.objects.filter(user=user, parent=root_folder)
    else:
        folders = PersonalFolder.objects.filter(user=user, parent__isnull=True)

    tree = []
    for folder in folders:
        folder_data = {
            "id": str(folder.id),
            "name": folder.name,
            "slug": folder.slug,
            "color": folder.color,
            "is_favorite": folder.is_favorite,
            "subfolders": get_folder_tree(
                user, root_folder=folder, include_files=include_files
            ),
        }

        if include_files:
            files = PersonalResource.objects.filter(
                user=user, folder=folder, is_deleted=False
            ).values("id", "title", "file_type", "file_size", "created_at")
            folder_data["files"] = list(files)

        tree.append(folder_data)

    return tree


def get_breadcrumbs(folder, include_current=True):
    """
    Generate breadcrumbs path from root to current folder.

    Algorithm: Iterative path reconstruction

    Args:
        folder: The folder to generate breadcrumbs for
        include_current: Whether to include the current folder

    Returns:
        List of breadcrumb dicts [{id, name, slug}, ...]
    """
    breadcrumbs = []
    current = folder

    while current:
        breadcrumbs.insert(
            0,
            {
                "id": str(current.id),
                "name": current.name,
                "slug": current.slug,
            },
        )
        current = current.parent

    if not include_current:
        breadcrumbs = breadcrumbs[:-1]

    return breadcrumbs


def get_all_descendant_folders(folder):
    """
    Get all descendant folders (children, grandchildren, etc.)

    Algorithm: Recursive DFS

    Returns:
        Set of all descendant folder IDs
    """
    descendants = set()
    stack = [folder]

    while stack:
        current = stack.pop()
        for subfolder in current.subfolders.all():
            descendants.add(subfolder.id)
            stack.append(subfolder)

    return descendants


def get_folder_depth(folder):
    """Calculate the depth level of a folder in the tree."""
    depth = 0
    current = folder.parent

    while current:
        depth += 1
        current = current.parent

    return depth


def validate_folder_move(folder, new_parent, user):
    """
    Validate folder move operation.

    Rules:
    - cannot move another user's folder
    - cannot move into another user's parent
    - cannot move folder into itself
    - cannot move folder into any descendant

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    if folder.user_id != user.id:
        return False, "Permission denied"

    if new_parent and new_parent.user_id != user.id:
        return False, "Cannot move folder into another user's folder"

    if new_parent is None:
        return True, None

    if new_parent.id == folder.id:
        return False, "Cannot move folder into itself"

    descendants = get_all_descendant_folders(folder)
    if new_parent.id in descendants:
        return False, "Cannot move folder into its descendant"

    return True, None


def build_comment_tree(resource, include_deleted=False):
    """
    Build threaded comments tree for a resource.

    Data Structure:
    - Dictionary map (comment_id -> node) for O(1) parent lookup
    - List for ordered root nodes
    """
    from apps.comments.models import Comment

    comments = (
        Comment.objects.filter(resource=resource)
        .select_related("user", "parent")
        .order_by("created_at")
    )
    if not include_deleted:
        comments = comments.filter(is_deleted=False)

    node_map = {}
    roots = []

    for comment in comments:
        content = comment.content if not comment.is_deleted else "[deleted]"
        node_map[comment.id] = {
            "id": str(comment.id),
            "comment": comment,
            "parent_id": str(comment.parent_id) if comment.parent_id else None,
            "user_id": str(comment.user_id),
            "content": content,
            "is_deleted": comment.is_deleted,
            "is_edited": comment.is_edited,
            "created_at": comment.created_at,
            "replies": [],
        }

    for comment in comments:
        node = node_map[comment.id]
        if comment.parent_id and comment.parent_id in node_map:
            node_map[comment.parent_id]["replies"].append(node)
        else:
            roots.append(node)

    return roots


def traverse_comment_tree(comment_tree):
    """
    Traverse comment tree in DFS order.

    Returns:
        list[dict]: flat list with `depth` metadata.
    """
    flattened = []
    stack = [(node, 0) for node in reversed(comment_tree)]

    while stack:
        node, depth = stack.pop()
        row = dict(node)
        row["depth"] = depth
        flattened.append(row)
        for reply in reversed(node.get("replies", [])):
            stack.append((reply, depth + 1))

    return flattened


# ==================== DUPLICATE DETECTION ALGORITHMS ====================


def detect_duplicate_bookmark(user, resource_id):
    """
    Check if user already bookmarked a resource.

    Returns:
        True if duplicate exists, False otherwise
    """
    from apps.bookmarks.models import Bookmark

    return Bookmark.objects.filter(user=user, resource_id=resource_id).exists()


def detect_duplicate_favorite(user, resource_id):
    """
    Check if user already favorited a resource.

    Returns:
        True if duplicate exists, False otherwise
    """
    from apps.favorites.models import Favorite, FavoriteType

    return Favorite.objects.filter(
        user=user, resource_id=resource_id, favorite_type=FavoriteType.RESOURCE
    ).exists()


def detect_duplicate_report(user, resource_id, reason_type, time_window_hours=24):
    """
    Check if user recently reported the same resource with same reason.

    Algorithm: Time-window based duplicate detection

    Args:
        user: The reporting user
        resource_id: The reported resource
        reason_type: The report reason
        time_window_hours: Hours to check for duplicates

    Returns:
        True if duplicate report exists, False otherwise
    """
    from apps.reports.models import Report

    time_threshold = timezone.now() - timezone.timedelta(hours=time_window_hours)

    return Report.objects.filter(
        reporter=user,
        resource_id=resource_id,
        reason_type=reason_type,
        created_at__gte=time_threshold,
    ).exists()


def detect_duplicate_filename(user, filename, folder=None, exclude_resource_id=None):
    """
    Check if filename already exists in user's library/folder.

    Args:
        user: The user
        filename: The filename to check
        folder: Optional folder to check in
        exclude_resource_id: ID to exclude (for updates)

    Returns:
        True if duplicate exists, False otherwise
    """
    from apps.resources.models import PersonalResource

    queryset = PersonalResource.objects.filter(user=user, title__iexact=filename)

    if folder:
        queryset = queryset.filter(folder=folder)
    else:
        queryset = queryset.filter(folder__isnull=True)

    if exclude_resource_id:
        queryset = queryset.exclude(id=exclude_resource_id)

    return queryset.exists()


def detect_duplicate_resource_upload(
    user, course_id, unit_id, title, time_window_days=7
):
    """
    Detect if same resource was uploaded recently with similar title.

    Algorithm: Fuzzy string matching with time window

    Returns:
        QuerySet of potential duplicates
    """
    from apps.resources.models import Resource

    time_threshold = timezone.now() - timezone.timedelta(days=time_window_days)

    return Resource.objects.filter(
        uploaded_by=user,
        course_id=course_id,
        unit_id=unit_id,
        created_at__gte=time_threshold,
    ).filter(Q(title__icontains=title) | Q(title__icontains=title[:20]))


# ==================== AGGREGATION ALGORITHMS ====================


def aggregate_user_activity(user, days=30):
    """
    Aggregate user's activity over a time period.

    Returns:
        Dict with aggregated activity metrics
    """
    from apps.activity.models import ActivityType, RecentActivity
    from apps.bookmarks.models import Bookmark
    from apps.downloads.models import Download
    from apps.favorites.models import Favorite, FavoriteType
    from apps.ratings.models import Rating

    time_threshold = timezone.now() - timezone.timedelta(days=days)

    return {
        "views": RecentActivity.objects.filter(
            user=user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            created_at__gte=time_threshold,
        ).count(),
        "downloads": Download.objects.filter(
            user=user, created_at__gte=time_threshold
        ).count(),
        "bookmarks": Bookmark.objects.filter(
            user=user, created_at__gte=time_threshold
        ).count(),
        "favorites": Favorite.objects.filter(
            user=user,
            favorite_type=FavoriteType.RESOURCE,
            created_at__gte=time_threshold,
        ).count(),
        "ratings": Rating.objects.filter(
            user=user, created_at__gte=time_threshold
        ).count(),
    }


def aggregate_resource_metrics(resource_ids):
    """
    Aggregate metrics for multiple resources.

    Returns:
        Dict with aggregated metrics
    """
    from apps.bookmarks.models import Bookmark
    from apps.downloads.models import Download
    from apps.favorites.models import Favorite, FavoriteType
    from apps.ratings.models import Rating
    from apps.resources.models import Resource

    resources = Resource.objects.filter(id__in=resource_ids)

    return {
        "total_resources": resources.count(),
        "total_downloads": Download.objects.filter(
            resource_id__in=resource_ids
        ).count(),
        "total_bookmarks": Bookmark.objects.filter(
            resource_id__in=resource_ids
        ).count(),
        "total_favorites": Favorite.objects.filter(
            resource_id__in=resource_ids, favorite_type=FavoriteType.RESOURCE
        ).count(),
        "avg_rating": Rating.objects.filter(resource_id__in=resource_ids).aggregate(
            avg=Avg("value")
        )["avg"]
        or 0,
    }


def aggregate_faculty_usage():
    """
    Aggregate resource usage by faculty.

    Returns:
        List of dicts with faculty usage stats
    """
    from django.db.models import Sum

    from apps.resources.models import Resource

    return list(
        Resource.objects.filter(status="approved", is_public=True)
        .values("faculty__name")
        .annotate(
            resource_count=Count("id"),
            total_downloads=Sum("download_count"),
            avg_rating=Avg("average_rating"),
        )
        .order_by("-resource_count")
    )


def aggregate_course_usage():
    """
    Aggregate resource usage by course.

    Returns:
        List of dicts with course usage stats
    """
    from apps.resources.models import Resource

    return list(
        Resource.objects.filter(status="approved", is_public=True)
        .values("course__name", "course__department__faculty__name")
        .annotate(
            resource_count=Count("id"),
            total_downloads=Sum("download_count"),
            avg_rating=Avg("average_rating"),
        )
        .order_by("-resource_count")
    )


# ==================== VALIDATION ALGORITHMS ====================


def validate_circular_folder_reference(folder, new_parent):
    """
    Validate that moving folder to new_parent won't create circular reference.

    Algorithm: Cycle detection in tree

    Returns:
        True if valid (no cycle), False if would create cycle
    """
    if new_parent is None:
        return True

    if new_parent.id == folder.id:
        return False

    # Check if new_parent is a descendant of folder
    descendants = get_all_descendant_folders(folder)
    return new_parent.id not in descendants


def validate_storage_quota(user, file_size):
    """
    Validate user has enough storage quota for upload.

    Returns:
        Tuple (is_valid, error_message)
    """
    from apps.resources.models import UserStorage

    try:
        storage = user.storage
    except UserStorage.DoesNotExist:
        storage = UserStorage.objects.create(user=user)

    if not storage.can_upload(file_size):
        return (
            False,
            f"Storage quota exceeded. You have {storage.get_usage_percentage():.1f}% used.",
        )

    return True, None


def validate_academic_hierarchy(faculty_id, department_id, course_id, unit_id):
    """
    Validate academic hierarchy correctness.

    Returns:
        Tuple (is_valid, error_message)
    """
    from apps.courses.models import Course, Unit
    from apps.faculties.models import Department, Faculty

    # Validate faculty exists
    if faculty_id:
        if not Faculty.objects.filter(id=faculty_id).exists():
            return False, "Invalid faculty"

    # Validate department belongs to faculty
    if department_id:
        department = Department.objects.filter(id=department_id).first()
        if not department:
            return False, "Invalid department"
        if faculty_id and department.faculty_id != faculty_id:
            return False, "Department does not belong to selected faculty"

    # Validate course belongs to department
    if course_id:
        course = Course.objects.filter(id=course_id).first()
        if not course:
            return False, "Invalid course"
        if department_id and course.department_id != department_id:
            return False, "Course does not belong to selected department"

    # Validate unit belongs to course
    if unit_id:
        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            return False, "Invalid unit"
        if course_id and unit.course_id != course_id:
            return False, "Unit does not belong to selected course"

    return True, None


def validate_file_type(extension, allowed_types=None):
    """
    Validate file type is allowed.

    Returns:
        True if valid, False otherwise
    """
    if allowed_types is None:
        allowed_types = {
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "txt",
            "jpg",
            "jpeg",
            "png",
            "gif",
            "zip",
            "rar",
        }

    return extension.lower() in allowed_types


# ==================== SORTING ALGORITHMS ====================


def sort_resources_by_criteria(resources, sort_by, ascending=False):
    """
    Sort resources by various criteria.

    Supported sort_by values:
    - 'newest' / 'oldest'
    - 'most_downloaded' / 'least_downloaded'
    - 'most_viewed' / 'least_viewed'
    - 'highest_rated' / 'lowest_rated'
    - 'name' / 'name_reverse'
    - 'size' / 'size_reverse'
    """
    reverse = not ascending

    sort_mapping = {
        "newest": lambda r: r.created_at,
        "oldest": lambda r: r.created_at,
        "most_downloaded": lambda r: getattr(r, "download_count", 0) or 0,
        "least_downloaded": lambda r: getattr(r, "download_count", 0) or 0,
        "most_viewed": lambda r: getattr(r, "view_count", 0) or 0,
        "least_viewed": lambda r: getattr(r, "view_count", 0) or 0,
        "highest_rated": lambda r: getattr(r, "average_rating", 0) or 0,
        "lowest_rated": lambda r: getattr(r, "average_rating", 0) or 0,
        "name": lambda r: (r.title or "").lower(),
        "name_reverse": lambda r: (r.title or "").lower(),
        "size": lambda r: getattr(r, "file_size", 0) or 0,
        "size_reverse": lambda r: getattr(r, "file_size", 0) or 0,
    }

    sort_func = sort_mapping.get(sort_by, lambda r: r.created_at)

    return sorted(resources, key=sort_func, reverse=reverse)


# ==================== RANKING ALGORITHMS ====================


def calculate_resource_score(resource, weights=None):
    """
    Calculate overall resource score based on multiple factors.

    Default weights:
    - downloads: 0.35
    - views: 0.20
    - rating: 0.25
    - recency: 0.20
    """
    if weights is None:
        weights = {
            "downloads": 0.35,
            "views": 0.20,
            "rating": 0.25,
            "recency": 0.20,
        }

    downloads = float(getattr(resource, "download_count", 0) or 0)
    views = float(getattr(resource, "view_count", 0) or 0)
    rating = float(getattr(resource, "average_rating", 0) or 0)

    # Recency score (1.0 for new, decaying over time)
    days_old = (timezone.now() - resource.created_at).days
    recency = max(0, 1 - (days_old / 365))  # Decay over a year

    score = (
        (downloads * weights.get("downloads", 0.35))
        + (views * weights.get("views", 0.20))
        + (rating * 5 * weights.get("rating", 0.25))  # Normalize to 5
        + (recency * 100 * weights.get("recency", 0.20))
    )

    return round(score, 2)


def rank_resources_by_score(resources, weights=None):
    """
    Rank resources by calculated score.

    Returns:
        List of resources sorted by score descending
    """
    scored = []
    for resource in resources:
        score = calculate_resource_score(resource, weights)
        scored.append((resource, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored]


def calculate_recommendation_score(
    resource, *, user_profile=None, behavior=None, weights=None
):
    """
    Weighted recommendation score combining engagement + academic match.

    Required signals:
    - views
    - downloads
    - favorites
    - ratings
    - faculty/department/course/year/semester match
    """
    if weights is None:
        weights = {
            "views": 0.20,
            "downloads": 0.45,
            "favorites": 0.10,
            "rating": 0.10,
            "academic": 0.15,
        }

    downloads = float(getattr(resource, "download_count", 0) or 0)
    views = float(getattr(resource, "view_count", 0) or 0)
    favorites = float(getattr(resource, "favorite_count", 0) or 0)
    rating = float(
        getattr(resource, "average_rating", 0)
        or getattr(resource, "rating_avg", 0)
        or 0
    )

    engagement_score = (
        (views * weights["views"])
        + (downloads * weights["downloads"])
        + (favorites * weights["favorites"])
        + (rating * weights["rating"])
    )

    academic_score = 0.0
    if user_profile:
        faculty_match = (
            1
            if user_profile.get("faculty_id")
            and user_profile.get("faculty_id") == resource.faculty_id
            else 0
        )
        department_match = (
            1
            if user_profile.get("department_id")
            and user_profile.get("department_id") == resource.department_id
            else 0
        )
        course_match = (
            1
            if user_profile.get("course_id")
            and user_profile.get("course_id") == resource.course_id
            else 0
        )
        year_match = (
            1
            if user_profile.get("year_of_study")
            and user_profile.get("year_of_study") == resource.year_of_study
            else 0
        )
        semester_match = (
            1
            if user_profile.get("semester")
            and str(user_profile.get("semester")) == str(resource.semester or "")
            else 0
        )

        course_match_score = (
            (faculty_match * 1)
            + (department_match * 2)
            + (course_match * 4)
            + (year_match * 2)
            + (semester_match * 1)
        )
        academic_score = course_match_score * weights["academic"]

    behavior_boost = 0.0
    if behavior:
        consumed_ids = behavior.get("consumed_ids", set())
        if getattr(resource, "id", None) in consumed_ids:
            behavior_boost -= 5.0
        if resource.course_id in behavior.get("preferred_courses", set()):
            behavior_boost += 1.0
        if resource.unit_id in behavior.get("preferred_units", set()):
            behavior_boost += 1.5

    return round(engagement_score + academic_score + behavior_boost, 4)


def calculate_related_resource_similarity(target_resource, candidate_resource):
    """
    Related resource similarity algorithm.

    Signals:
    - same unit (strongest)
    - same course
    - tag overlap
    - same type
    """
    score = 0

    if (
        target_resource.unit_id
        and target_resource.unit_id == candidate_resource.unit_id
    ):
        score += 5
    if (
        target_resource.course_id
        and target_resource.course_id == candidate_resource.course_id
    ):
        score += 3

    target_tags = {
        tag.strip().lower()
        for tag in (target_resource.tags or "").split(",")
        if tag.strip()
    }
    candidate_tags = {
        tag.strip().lower()
        for tag in (candidate_resource.tags or "").split(",")
        if tag.strip()
    }
    overlap = target_tags & candidate_tags
    score += len(overlap) * 2

    if (
        target_resource.resource_type
        and target_resource.resource_type == candidate_resource.resource_type
    ):
        score += 1

    return score


def calculate_search_relevance(resource, query):
    """
    Search relevance algorithm with popularity blending.

    Signals:
    - exact title match
    - partial title match
    - tag match
    - course/unit match
    - popularity (downloads + views + rating)
    """
    query = (query or "").strip().lower()
    if not query:
        return 0

    title = (resource.title or "").lower()
    description = (resource.description or "").lower()
    tags = (resource.tags or "").lower()
    course_name = getattr(resource.course, "name", "") or ""
    unit_name = getattr(resource.unit, "name", "") or ""
    course_name = course_name.lower()
    unit_name = unit_name.lower()

    score = 0.0
    if title == query:
        score += 10
    elif title.startswith(query):
        score += 7
    elif query in title:
        score += 5

    if query in tags:
        score += 4
    if query in course_name:
        score += 4
    if query in unit_name:
        score += 3
    if query in description:
        score += 2

    downloads = float(getattr(resource, "download_count", 0) or 0)
    views = float(getattr(resource, "view_count", 0) or 0)
    rating = float(getattr(resource, "average_rating", 0) or 0)
    popularity = min((downloads * 0.03) + (views * 0.01) + (rating * 0.2), 3.0)

    return round(score + popularity, 4)


def aggregate_usage_dictionaries(days=30):
    """
    Build analytics dictionaries for dashboard charts.

    Returns:
        dict with:
        - downloads_by_course
        - views_by_unit
        - favorites_by_resource
        - active_users_by_faculty
    """
    from apps.activity.models import RecentActivity
    from apps.favorites.models import Favorite, FavoriteType
    from apps.resources.models import Resource

    since = timezone.now() - timezone.timedelta(days=days)

    downloads_by_course = defaultdict(int)
    for row in (
        Resource.objects.filter(status="approved", is_public=True)
        .values("course__name")
        .annotate(total=Sum("download_count"))
    ):
        key = row.get("course__name") or "Unknown"
        downloads_by_course[key] = int(row.get("total") or 0)

    views_by_unit = defaultdict(int)
    for row in (
        Resource.objects.filter(status="approved", is_public=True)
        .values("unit__name")
        .annotate(total=Sum("view_count"))
    ):
        key = row.get("unit__name") or "Unknown"
        views_by_unit[key] = int(row.get("total") or 0)

    favorites_by_resource = defaultdict(int)
    for row in (
        Favorite.objects.filter(
            favorite_type=FavoriteType.RESOURCE,
            created_at__gte=since,
            resource__isnull=False,
        )
        .values("resource__title")
        .annotate(total=Count("id"))
    ):
        key = row.get("resource__title") or "Unknown"
        favorites_by_resource[key] = int(row.get("total") or 0)

    active_users_by_faculty = defaultdict(int)
    for row in (
        RecentActivity.objects.filter(created_at__gte=since)
        .values("user__faculty__name")
        .annotate(total=Count("user", distinct=True))
    ):
        key = row.get("user__faculty__name") or "Unknown"
        active_users_by_faculty[key] = int(row.get("total") or 0)

    return {
        "downloads_by_course": dict(downloads_by_course),
        "views_by_unit": dict(views_by_unit),
        "favorites_by_resource": dict(favorites_by_resource),
        "active_users_by_faculty": dict(active_users_by_faculty),
    }


def rank_analytics_entities(metric_map, limit=10, reverse=True):
    """
    Rank dictionary entities by value.

    Example:
    {'BSc CS': 120, 'BEd': 30} -> [('BSc CS', 120), ('BEd', 30)]
    """
    if not metric_map:
        return []
    return sorted(metric_map.items(), key=lambda item: item[1], reverse=reverse)[
        : max(1, limit)
    ]


def deduplicate_resources(resources):
    """Deduplicate resources while preserving original order using a set."""
    seen = set()
    unique = []
    for resource in resources:
        resource_id = getattr(resource, "id", None)
        if not resource_id or resource_id in seen:
            continue
        seen.add(resource_id)
        unique.append(resource)
    return unique
