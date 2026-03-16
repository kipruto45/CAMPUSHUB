"""
Automation services for resources app.
"""

import logging
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.ratings.models import Rating

from .models import PersonalFolder, PersonalResource, Resource, UserStorage

logger = logging.getLogger(__name__)


# =============================================================================
# FILE VALIDATION ALGORITHM
# =============================================================================

ALLOWED_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "txt",
    "zip",
    "rar",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "mp4",
    "mp3",
]
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def validate_file(file):
    """
    File validation algorithm.
    Validates file extension and size.

    Returns:
        tuple: (is_valid, error_message)
    """
    # Check extension
    extension = file.name.split(".")[-1].lower() if "." in file.name else ""

    if extension not in ALLOWED_EXTENSIONS:
        return (
            False,
            f"File type .{extension} is not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check size
    if file.size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        file_mb = file.size / (1024 * 1024)
        return (
            False,
            f"File size ({file_mb:.1f}MB) exceeds maximum allowed size ({max_mb:.0f}MB)",
        )

    return True, None


def detect_duplicate_file(user, file_name, title=None):
    """
    Duplicate detection algorithm.
    Checks for similar filenames or titles.

    Returns:
        Resource or None if no duplicate found
    """
    # Normalize filename
    normalized_name = file_name.lower().strip()

    # Check by exact filename
    duplicates = Resource.objects.filter(
        uploaded_by=user, file__icontains=normalized_name
    )

    if duplicates.exists():
        return duplicates.first()

    # Check by title if provided
    if title:
        title_duplicates = Resource.objects.filter(
            uploaded_by=user, title__iexact=title
        )
        if title_duplicates.exists():
            return title_duplicates.first()

    return None


# =============================================================================
# TRENDING SCORE ALGORITHM
# =============================================================================


def calculate_trending_score(resource):
    """
    Trending score algorithm.
    trending_score = (views * 0.2) + (downloads * 0.5) + (bookmarks * 0.2) + (recent_comments * 0.1)
    """
    # Count recent comments (last 7 days)
    recent_comments = resource.comments.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()

    # Calculate score
    score = (
        (resource.view_count * 0.2)
        + (resource.download_count * 0.5)
        + (resource.bookmarks.count() * 0.2)
        + (recent_comments * 0.1)
    )

    return round(score, 2)


def get_trending_resources(limit=10):
    """
    Get trending resources based on trending score.
    """
    resources = Resource.objects.filter(status="approved", is_public=True)

    # Annotate with counts
    resources = resources.annotate(
        comment_count=Count(
            "comments",
            filter=Q(comments__created_at__gte=timezone.now() - timedelta(days=7)),
        )
    )

    # Calculate trending score for each resource
    trending = []
    for resource in resources:
        score = calculate_trending_score(resource)
        trending.append((resource, score))

    # Sort by score and return top results
    trending.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in trending[:limit]]


# =============================================================================
# RECOMMENDATION ALGORITHM
# =============================================================================


def calculate_recommendation_score(resource, user):
    """
    Recommendation score algorithm.
    recommendation_score = course_match + tag_similarity + saved_similarity + popularity_weight
    """
    score = 0.0

    # Course match (30 points max)
    if getattr(user, "course", None) and resource.course:
        if user.course == resource.course:
            score += 30

    # Tag similarity (20 points max)
    if resource.tags:
        user_interest_raw = getattr(getattr(user, "profile", None), "interests", "")
        user_tags = set(user_interest_raw.split(",") if user_interest_raw else [])
        resource_tags = set(resource.tags.split(","))
        if user_tags & resource_tags:  # intersection
            score += min(20, len(user_tags & resource_tags) * 5)

    # Saved/bookmarked similarity (30 points max)
    user_bookmarks = Bookmark.objects.filter(user=user).values_list(
        "resource_id", flat=True
    )
    if resource.id in user_bookmarks:
        score += 10

    # Popularity weight (20 points max)
    if resource.average_rating:
        score += min(20, float(resource.average_rating) * 4)

    return round(score, 2)


def get_recommended_resources(user, limit=10):
    """
    Get personalized recommendations for a user.
    """
    # Get resources user hasn't interacted with
    interacted = set()
    interacted.update(
        Bookmark.objects.filter(user=user).values_list("resource_id", flat=True)
    )
    interacted.update(
        Rating.objects.filter(user=user).values_list("resource_id", flat=True)
    )
    interacted.update(
        Download.objects.filter(user=user).values_list("resource_id", flat=True)
    )

    # Get candidate resources
    candidates = Resource.objects.filter(status="approved", is_public=True).exclude(
        id__in=interacted
    )

    # Calculate scores
    recommendations = []
    for resource in candidates:
        score = calculate_recommendation_score(resource, user)
        if score > 0:
            recommendations.append((resource, score))

    # Sort by score
    recommendations.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in recommendations[:limit]]


# =============================================================================
# MODERATION PRIORITY ALGORITHM
# =============================================================================


def calculate_moderation_priority(resource):
    """
    Moderation priority algorithm.
    priority = number_of_reports + severity_weight + recent_activity_weight
    """
    from apps.reports.models import Report

    # Count reports
    report_count = Report.objects.filter(resource=resource).count()

    # Calculate severity based on report types
    severe_reports = Report.objects.filter(
        resource=resource, reason_type__in=["copyright", "abusive"]
    ).count()

    # Recent activity (last 24 hours)
    recent_views = resource.view_count
    recent_downloads = resource.download_count

    # Calculate priority score
    priority = (
        report_count * 10
        + severe_reports * 20
        + (recent_views / 100)
        + (recent_downloads * 0.5)
    )

    return round(priority, 2)


# =============================================================================
# SEARCH RANKING ALGORITHM
# =============================================================================


def calculate_search_relevance(resource, query):
    """
    Search relevance ranking algorithm.
    Considers title match, description match, tag match, and popularity.
    """
    query = query.lower()
    score = 0.0

    # Title match (highest weight)
    if resource.title.lower() == query:
        score += 100
    elif query in resource.title.lower():
        score += 50
    elif resource.title.lower().startswith(query):
        score += 75

    # Description match
    if resource.description:
        if query in resource.description.lower():
            score += 25

    # Tag match
    if resource.tags:
        tags = [t.strip().lower() for t in resource.tags.split(",")]
        for tag in tags:
            if query == tag:
                score += 40
            elif query in tag:
                score += 20

    # Popularity boost
    score += resource.view_count * 0.1
    score += resource.download_count * 0.5
    if resource.average_rating:
        score += float(resource.average_rating) * 2

    return round(score, 2)


# =============================================================================
# STORAGE CALCULATION ALGORITHM
# =============================================================================


def calculate_storage_usage(user):
    """
    Calculate storage usage for a user.
    """
    # Get personal resources
    personal_size = (
        PersonalResource.objects.filter(user=user).aggregate(total=Sum("file_size"))[
            "total"
        ]
        or 0
    )

    # Get public uploads
    public_size = (
        Resource.objects.filter(uploaded_by=user).aggregate(total=Sum("file_size"))[
            "total"
        ]
        or 0
    )

    return {
        "personal": personal_size,
        "public": public_size,
        "total": personal_size + public_size,
    }


def check_storage_limit(user, file_size):
    """
    Check if user can upload file based on storage limit.
    """
    storage, created = UserStorage.objects.get_or_create(user=user)

    # Get user's current storage usage
    usage = calculate_storage_usage(user)

    # Check if within limit
    return (usage["total"] + file_size) <= storage.storage_limit


# =============================================================================
# RECENT FILES TRACKING
# =============================================================================


def update_recent_files(user, resource):
    """
    Update recently accessed files.
    """
    if hasattr(resource, "mark_accessed"):
        resource.mark_accessed()


# =============================================================================
# AUTO TAGGING ALGORITHM
# =============================================================================


def suggest_tags(title, description="", resource_type=""):
    """
    Smart tagging algorithm.
    Suggests tags based on title, description, and resource type.
    """
    tags = set()

    # Common keywords
    keyword_tags = {
        "exam": ["exam", "examination", "test"],
        "notes": ["notes", "lecture notes", "summary"],
        "assignment": ["assignment", "homework", "task"],
        "tutorial": ["tutorial", "guide", "how-to"],
        "past paper": ["past paper", "previous exam", "old exam"],
        "slides": ["slides", "presentation", "ppt"],
        "project": ["project", "final year"],
        "lab": ["lab", "laboratory", "practical"],
    }

    text = f"{title} {description} {resource_type}".lower()

    for tag, keywords in keyword_tags.items():
        for keyword in keywords:
            if keyword in text:
                tags.add(tag)
                break

    # Add resource type as tag
    if resource_type:
        tags.add(resource_type)

    return list(tags)[:10]  # Limit to 10 tags


# =============================================================================
# FOLDER TREE ALGORITHM
# =============================================================================


def get_folder_tree(user, parent=None):
    """
    Get hierarchical folder tree.
    """
    if parent:
        folders = PersonalFolder.objects.filter(user=user, parent=parent)
    else:
        folders = PersonalFolder.objects.filter(user=user, parent__isnull=True)

    tree = []
    for folder in folders:
        tree.append(
            {
                "id": str(folder.id),
                "name": folder.name,
                "color": folder.color,
                "is_favorite": folder.is_favorite,
                "subfolders": get_folder_tree(user, folder),
                "file_count": folder.personal_resources.count(),
                "total_size": folder.get_total_size(),
            }
        )

    return tree


def get_folder_breadcrumbs(folder):
    """
    Generate breadcrumbs for a folder.
    """
    breadcrumbs = []
    current = folder

    while current:
        breadcrumbs.insert(0, {"id": str(current.id), "name": current.name})
        current = current.parent

    return breadcrumbs


# =============================================================================
# ANALYTICS ALGORITHMS
# =============================================================================


def calculate_engagement_score(resource):
    """
    Calculate engagement score for analytics.
    """
    # Calculate based on multiple factors
    views_weight = 1.0
    downloads_weight = 3.0
    bookmarks_weight = 5.0
    comments_weight = 4.0
    ratings_weight = 2.0

    score = (
        resource.view_count * views_weight
        + resource.download_count * downloads_weight
        + resource.bookmarks.count() * bookmarks_weight
        + resource.comments.count() * comments_weight
        + (float(resource.average_rating or 0) * 10 * ratings_weight)
    )

    return round(score, 2)


def get_top_uploaders(days=30, limit=10):
    """
    Get most active uploaders.
    """
    since = timezone.now() - timedelta(days=days)

    top = (
        Resource.objects.filter(created_at__gte=since, status="approved")
        .values("uploaded_by__id", "uploaded_by__full_name")
        .annotate(upload_count=Count("id"))
        .order_by("-upload_count")[:limit]
    )

    return list(top)


def get_course_popularity():
    """
    Calculate course popularity based on resources and downloads.
    """
    from apps.courses.models import Course

    courses = Course.objects.annotate(
        resource_count=Count("resources"),
        total_downloads=Sum("resources__download_count"),
    ).order_by("-total_downloads")

    return [
        {
            "course": c.name,
            "code": c.code,
            "resources": c.resource_count,
            "downloads": c.total_downloads or 0,
        }
        for c in courses
    ]


# =============================================================================
# NOTIFICATION PRIORITY LOGIC
# =============================================================================


def get_notification_priority(notification_type):
    """
    Get notification priority for batching.
    """
    priority_map = {
        "resource_approved": 1,
        "resource_rejected": 1,
        "new_comment": 2,
        "reply_comment": 2,
        "new_resource": 3,
        "trending": 5,
        "announcement": 1,
    }
    return priority_map.get(notification_type, 5)
